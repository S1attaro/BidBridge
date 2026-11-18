"""Make SAM.gov notices easier to scan.

- short_title: "REQUEST FOR PROPOSAL (RFP) N4008427R1027 - FY27 SPECIAL PROJECT ..." becomes "Special Project ...".
  The full title is kept and shown on the job's details.
- is_goods: product buys (bolts, flour, seal rings) aren't work a contractor does on site.
- dupe_key: agencies repost a job each time they change it. Every copy has the same solicitation number.

These take plain strings so the data migration can use them too.
"""

import re

from .codes import KEEP_UPPER

MAX_LEN = 80

# Words that only say what kind of notice it is. The list already shows that.
NOTICE_WORDS = re.compile(
    r"^(?:amend(?:ment)?\s*\d*|vendor\s+opportunity|notice\s+of\s+intent(?:\s+to)?|notice(?:\s+for)?|request\s+for\s+(?:quotations?|quotes?|proposals?|information)|"
    r"sources?\s+sought(?:\s+notice)?|pre-?solicitation(?:\s+notice)?|combined\s+synopsis\s*/\s*solicitation|"
    r"synopsis|solicitation|special\s+notice|rfq|rfp|rfi|ifb|new|"
    r"(?:number|no\.?|#)\s*:?)\b\s*[-:|,]*\s*(?:for|to)?\s*",
    re.I,
)
# Contract-type jargon a tradesperson doesn't need in a title.
JARGON = re.compile(
    r"\b(?:single|multiple)[\s-]award\s+task\s+order\s+contracts?|indefinite[\s/-]+delivery[\s/,-]+indefinite[\s/-]+quantity|"
    r"blanket\s+purchase\s+agreements?|(?:total\s+)?small[\s-]business\s+set[\s-]aside|set[\s-]aside|"
    r"continuously\s+open\s+solicitation|\bidiq\b(?:\s+contracts?)?|\bsatoc\b|\bmatoc\b|\bbpa\b",
    re.I,
)
LEAD_WORDS = re.compile(r"^(?:provide|providing|provision\s+of|procurement\s+of|acquisition\s+of|requirements?\s+(?:for|to)|for|to|of|the)\s+", re.I)
PSC_PREFIX = re.compile(r"^[A-Z0-9]{1,4}--\s*")
FISCAL_YEAR = re.compile(r"\bFY\s?\d{2,4}\b:?", re.I)
# Solicitation numbers and other codes: 6+ characters with both digits and letters or dashes.
CODE = re.compile(r"(?:\b(?:Nos?\.?|Numbers?:?|#)\s*)?\b(?=[A-Z0-9-]*\d)(?=[A-Z0-9-]*[A-Z-])[A-Z0-9][A-Z0-9-]{5,}\b|\b\d{6,}\b", re.I)
PART_NUMBERS = re.compile(r"\b\d{4}[- ]\d{2}[- ]\d{3}[- ]\d{4}\b|\b(?:NSN|P/?N)\b[:#]?", re.I)
# A notice-type word left at the end, like ": Request for Proposal (RFP)".
TRAILING_NOTICE = re.compile(
    r"[\s:,-]*\b(?:request\s+for\s+(?:proposals?|quot\w*|information)|rfp|rfq|rfi|solicitation|sources\s+sought)(?:\s*\(s\))?$", re.I)
# One-word acronyms in parentheses with mixed case, like (DoWEA) or (CATP2).
ACRONYM_PARENS = re.compile(r"\s*\((?=[^()\s]*[A-Z][^()\s]*[A-Z])[^()\s]{2,12}\)")
# Parentheses with no lowercase letters are acronyms or codes, like (SATOC) or (RFP).
CAPS_PARENS = re.compile(r"\s*\([^()a-z]*\)")
SMALL_WORDS = {"a", "an", "and", "at", "by", "for", "in", "of", "on", "or", "the", "to", "with"}
COMMON_SHORT = {"AND", "THE", "FOR", "OF", "AT", "IN", "ON", "TO", "NEW", "BAY", "AIR", "WAR", "SEA", "BIG", "OLD", "ROW", "LOT"}
EDGE = " -–:|,/.;"


def _is_shouting(text):
    letters = [ch for ch in text if ch.isalpha()]
    return len(letters) > 8 and sum(ch.isupper() for ch in letters) / len(letters) > 0.7


def _word_case(word, first):
    parts = []
    for part in word.split("-"):
        bare = part.strip(",.()&'").upper()
        if bare in KEEP_UPPER or any(ch.isdigit() for ch in part) or (2 <= len(bare) <= 3 and bare not in COMMON_SHORT):
            parts.append(part.upper())
        elif not first and part.lower() in SMALL_WORDS:
            parts.append(part.lower())
        else:
            parts.append(part[:1].upper() + part[1:].lower())
    return "-".join(parts)


def fix_case(text):
    if not _is_shouting(text):
        return text
    return " ".join(_word_case(w, i == 0) for i, w in enumerate(text.split()))


def _tidy(text):
    text = text.replace("—", " - ").replace("–", " - ").replace("_", " ")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"(\w)- ", r"\1 - ", text)
    text = re.sub(r"\s+([,.:;)])", r"\1", text)
    text = re.sub(r"([-–:|,/])(\s*[-–:|,/])+", r"\1", text)
    return text.strip(EDGE)


def _shorten(text, max_len=MAX_LEN):
    if len(text) <= max_len:
        return text
    # The place is shown under the title, so a trailing "at the ...", "in ...", or ", City, ST" can go.
    # Never cut at a dash or colon: the part after one is often the actual job.
    # The tail has to be short enough to be a place, so a list like "Hazardous, Toxic, and ..." stays whole.
    for cut, tail_words in ((" at ", 8), (" in ", 6), (", ", 4)):
        if cut not in text:
            continue
        head, tail = text.split(cut, 1)
        head = head.strip(EDGE)
        # Keep enough words that the title still says what the work is.
        if 25 <= len(head) <= max_len and len(head.split()) >= 4 and len(tail.split()) <= tail_words:
            return head
    words = text[: max_len - 1].rsplit(" ", 1)[0].strip(EDGE)
    if words.count("(") > words.count(")"):
        words = words[: words.rfind("(")].strip(EDGE)
    return _drop_dangling(words) + "…"


def _drop_dangling(text):
    """No title should end on "of", "for", "and", and so on."""
    words = text.split()
    while len(words) > 1 and words[-1].lower().strip(EDGE) in SMALL_WORDS:
        words.pop()
    return " ".join(words).strip(EDGE)


def short_title(title, max_len=MAX_LEN):
    original = _tidy(title or "")
    text = _tidy(PSC_PREFIX.sub("", (title or "").strip()))
    text = re.sub(r"\bPSC\s+[A-Z0-9]{3,4}\b", "", text)
    text = CAPS_PARENS.sub("", text)
    text = ACRONYM_PARENS.sub("", text)
    text = PART_NUMBERS.sub("", text)
    text = FISCAL_YEAR.sub("", text)
    text = CODE.sub("", text)
    text = JARGON.sub("", text)
    text = _tidy(text)
    for _ in range(4):
        before = text
        text = _tidy(NOTICE_WORDS.sub("", text, count=1))
        text = _tidy(LEAD_WORDS.sub("", text, count=1))
        if text == before:
            break
    text = re.sub(r"\s+(?:solicitation|contract)$", "", text, flags=re.I)
    text = _drop_dangling(_tidy(TRAILING_NOTICE.sub("", text)))
    # "EHRM | EHRM Training and Administrative Space Construction": keep the part that says the most.
    if " | " in text:
        text = max((_tidy(part) for part in text.split(" | ")), key=lambda part: len(part.split()))
    if len(re.sub(r"[^A-Za-z]", "", text)) < 4:
        text = original
    text = fix_case(text)
    return _shorten(text[:1].upper() + text[1:], max_len)


def is_goods(psc_code, title=""):
    """Product codes (PSC/FSC) are all numbers. Service and construction codes start with a letter."""
    psc = (psc_code or "").strip()
    if psc:
        return psc[0].isdigit()
    return bool(re.match(r"^\d{2}--", title or ""))


def dupe_key(solicitation_number, department, title, office, due_date):
    """Copies of one job share a solicitation number. Without one, match on title, office, and due day."""
    sol = re.sub(r"[^A-Z0-9]", "", (solicitation_number or "").upper())
    if sol:
        return f"s|{(department or '').upper()[:60]}|{sol}"[:200]
    day = due_date.date().isoformat() if due_date else ""
    return f"t|{(title or '').lower()[:120]}|{(office or '').upper()[:40]}|{day}"[:200]


def tell_apart(title, solicitation_number):
    """A short tag that separates jobs with the same short title, like "No. 2-2025"."""
    found = re.search(r"\bNos?\.\s*([A-Z0-9][A-Z0-9-]*\d[A-Z0-9-]*)", title or "", re.I)
    if found:
        return f"No. {found.group(1)}"
    return solicitation_number or ""
