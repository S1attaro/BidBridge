"""Plain summaries of contract postings.

Steps:
  1. Get the posting text. If we only have a SAM.gov link, fetch it (uses one SAM.gov call).
  2. Clean it: drop HTML, emails, and phone numbers, then keep the first MAX_CHARS characters.
  3. Send it with the key facts to the Groq model and ask for JSON.
  4. Check every value. A number the model writes must be in the posting, or it is thrown out.
     Due dates and places always come from the SAM.gov fields, never from the model.
  5. Save the summary so each contract is only summarized once.

If Groq is down, out of calls, or has no key, a simple summary is built from the
SAM.gov fields instead, so the page always works.
"""

import html
import json
import logging
import re
import time

from django.conf import settings
from django.utils import timezone

from contracts import clients, codes
from contracts.clients import ApiError

from .models import AIRequestLog, ContractSummary

# Any OpenAI-style chat service works here (Groq by default, or UIUC's Lumen). Set AI_BASE_URL in .env.
def chat_url():
    return settings.AI_BASE_URL.rstrip("/") + "/chat/completions"
MAX_CHARS = 3500
SAM_CALLS_TO_KEEP = 2  # leave a few SAM.gov calls for the daily update

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You explain U.S. government contract postings to owners of small trade businesses.
Many readers are not native English speakers. Write at a 5th to 6th grade reading level.
Use short sentences and common words. No legal words.

Reply with one JSON object and nothing else. Use exactly these keys:
summary, job, requirements, skills, key_dates

- summary: 2 or 3 short sentences. Say what work is needed and anything big a bidder must know.
- job: the work in 3 to 8 words, like "Replace roof on one building".
- requirements: a list of 3 to 5 short items a bidder must have or do (licenses, insurance, site visit, deadlines for the work, background checks). Use [] if none are given.
- skills: a list of 1 to 5 trade skills needed, like "roofing" or "HVAC repair".
- key_dates: dates a bidder must not miss, other than the bid due date. A list of objects like
  {"what": "Site visit", "when": "Nov 30, 2026 at 9:00 AM"}. Use labels like "Site visit" or
  "Questions due". Copy the date from the posting. Use [] if the posting gives none.

Rules:
- Only use facts from the posting. Do not guess. If something is not in the posting, leave it out.
- Do not put the bid due date in the summary. Do not include phone numbers, emails, or names of people.
"""


# ---------- getting and cleaning the text ----------

def clean_text(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "[email]", text)
    text = re.sub(r"\(?\b\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b", "[phone]", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_CHARS]


def posting_text(contract, allow_fetch=False):
    """The posting's full text. Fetches it from SAM.gov only when allowed and calls are left."""
    if contract.description_text:
        return contract.description_text
    if not (allow_fetch and contract.description_url and settings.SAM_API_KEY):
        return ""
    if clients.sam_calls_left() <= SAM_CALLS_TO_KEEP:
        return ""
    try:
        text = clients.fetch_description(contract.description_url)
    except ApiError as e:
        log.warning("Could not fetch description for %s: %s", contract.notice_id, e)
        return ""
    contract.description_text = text
    contract.description_fetched = True
    contract.save(update_fields=["description_text", "description_fetched", "updated"])
    return text


def facts(contract):
    lines = [
        f"Title: {contract.title}",
        f"Agency: {contract.agency.short_name if contract.agency else 'not listed'}",
        f"Place: {contract.place or 'not listed'}",
        f"Type of work: {contract.trade_name or 'other'} (NAICS {contract.naics_code or 'none'})",
        f"Who can bid: {contract.set_aside_name}",
    ]
    return "\n".join(lines)


# ---------- Groq ----------

def parse_model_json(content):
    try:
        return json.loads(content)
    except (TypeError, json.JSONDecodeError):
        match = re.search(r"\{.*\}", content or "", re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return None


def ask_groq(user_message, feature="summary"):
    """Send one chat request. Returns the parsed JSON dict, or raises ApiError."""
    if not settings.GROQ_API_KEY:
        raise ApiError("GROQ_API_KEY is not set")
    body = {
        "model": settings.GROQ_MODEL,
        "temperature": 0,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_message}],
        "response_format": {"type": "json_object"},
    }
    if "gpt-oss" in settings.GROQ_MODEL:
        body["reasoning_effort"] = "low"
    headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}"}

    start = time.monotonic()
    try:
        data = clients.post_json("groq", chat_url(), body, headers=headers)
    except ApiError as e:
        log_request(feature, start, ok=False, error=str(e))
        raise
    usage = data.get("usage") or {}
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        log_request(feature, start, usage, ok=False, error="unexpected response")
        raise ApiError("groq returned an unexpected response")
    parsed = parse_model_json(content)
    if not isinstance(parsed, dict):
        log_request(feature, start, usage, ok=False, error="not JSON")
        raise ApiError("groq did not return JSON")
    log_request(feature, start, usage)
    return parsed


def log_request(feature, start, usage=None, ok=True, error=""):
    usage = usage or {}
    AIRequestLog.objects.create(
        feature=feature,
        engine="groq",
        model_name=settings.GROQ_MODEL,
        prompt_tokens=usage.get("prompt_tokens") or 0,
        completion_tokens=usage.get("completion_tokens") or 0,
        latency_ms=int((time.monotonic() - start) * 1000),
        ok=ok,
        error=error[:300],
    )


# ---------- checking the values ----------

def numbers_in(text):
    return set(re.findall(r"\d+(?:[.,]\d+)*", text or ""))


def made_up_numbers(text, source):
    """Numbers in text that don't appear anywhere in the source."""
    allowed = {n.replace(",", "") for n in numbers_in(source)}
    return [n for n in numbers_in(text) if n.replace(",", "") not in allowed]


def short_list(value, max_items, max_len, source, warnings, label):
    if not isinstance(value, list):
        return []
    items = []
    for item in value:
        item = str(item).strip()
        if not item or len(item) > max_len:
            continue
        if made_up_numbers(item, source):
            warnings.append(f"Dropped a {label} with a number that isn't in the posting.")
            continue
        items.append(item)
    return items[:max_items]


def check_values(raw, source):
    """Keep only values that look right. Returns (clean dict, warnings)."""
    warnings = []
    summary = str(raw.get("summary") or "").strip()
    sentences = re.split(r"(?<=[.!?])\s+", summary)
    kept = [s for s in sentences if s and not made_up_numbers(s, source)]
    if len(kept) < len([s for s in sentences if s]):
        warnings.append("Dropped a summary sentence with a number that isn't in the posting.")
    summary = " ".join(kept)[:700]

    job = str(raw.get("job") or "").strip()
    if len(job) > 120 or made_up_numbers(job, source):
        job = ""

    return {
        "summary": summary,
        "job": job,
        "requirements": short_list(raw.get("requirements"), 5, 160, source, warnings, "requirement"),
        "skills": short_list(raw.get("skills"), 5, 40, source, warnings, "skill"),
        "key_dates": check_dates(raw.get("key_dates"), source, warnings),
    }, warnings


def check_dates(value, source, warnings):
    """Keep a key date only if its numbers really appear in the posting."""
    if not isinstance(value, list):
        return []
    kept = []
    for item in value[:4]:
        if not isinstance(item, dict):
            continue
        what = str(item.get("what") or "").strip()[:30]
        when = str(item.get("when") or "").strip()[:40]
        if not what or not when or not numbers_in(when):
            continue
        if made_up_numbers(when, source):
            warnings.append(f"Dropped the date for {what.lower()} because it isn't in the posting.")
            continue
        kept.append({"what": what, "when": when})
    return kept[:3]


# ---------- simple summary (no AI) ----------

def requirement_sentences(text, limit=3):
    sentences = re.split(r"(?<=[.!?])\s+", clean_text(text))
    picked = [s for s in sentences if re.search(r"\b(must|required|shall|need to)\b", s, re.I) and len(s) < 200]
    return picked[:limit]


def simple_summary(contract, text=""):
    agency = contract.agency.short_name if contract.agency else "A federal agency"
    work = (contract.trade_name or "work").lower()
    place = f" in {contract.place}" if contract.place else ""
    parts = [f"{agency} needs {work}{place}.", f"The job is: {contract.title}."]
    who = codes.set_aside_who(contract.set_aside)
    parts.append(f"Only {who} can bid." if who else "Any business can bid.")
    return {
        "summary": " ".join(parts),
        "job": contract.title[:120],
        "requirements": requirement_sentences(text),
        "skills": [contract.trade_name] if contract.trade_name else [],
        "key_dates": [],
    }


# ---------- reading level ----------

def syllables(word):
    word = word.lower()
    groups = re.findall(r"[aeiouy]+", word)
    count = len(groups)
    if word.endswith("e") and count > 1 and not word.endswith("le"):
        count -= 1
    return max(count, 1)


def reading_grade(text):
    """Flesch-Kincaid grade level. About 5 to 6 is the goal."""
    words = re.findall(r"[A-Za-z]+", text or "")
    sentences = max(len(re.findall(r"[.!?]+", text or "")), 1)
    if not words:
        return None
    syllable_count = sum(syllables(w) for w in words)
    grade = 0.39 * len(words) / sentences + 11.8 * syllable_count / len(words) - 15.59
    return round(grade, 1)


# ---------- main entry point ----------

def summarize(contract, use_ai=True, allow_fetch=False):
    """Make (or remake) the summary for one contract and save it."""
    text = posting_text(contract, allow_fetch)
    source_text = facts(contract) + "\n" + clean_text(text)
    fields, warnings, source, model_name = None, [], "simple", ""

    if use_ai:
        message = facts(contract) + "\n\nPosting:\n" + (clean_text(text) or "(no full text, use the facts above)")
        try:
            raw = ask_groq(message)
            fields, warnings = check_values(raw, source_text)
            if fields["summary"]:
                source, model_name = "ai", settings.GROQ_MODEL
            else:
                warnings.append("The AI summary didn't pass our checks.")
                fields = None
        except ApiError as e:
            log.warning("Groq summary failed for %s: %s", contract.notice_id, e)
            warnings.append("The AI was not available.")

    if fields is None:
        fields = simple_summary(contract, text)

    summary, _ = ContractSummary.objects.update_or_create(
        contract=contract,
        defaults={
            **fields,
            "source": source,
            "model_name": model_name,
            "used_full_text": bool(text),
            "reading_grade": reading_grade(fields["summary"]),
            "warnings": warnings,
            "created_at": timezone.now(),
        },
    )
    return summary
