# BidBridge AI

How the AI parts of BidBridge work. The evaluation section is filled in for the final.

## Overview

| Feature | Method | Where |
|---|---|---|
| Plain summaries | LLM (`openai/gpt-oss-20b` on Groq) | `summaries/ai.py` |
| My matches | Hard filters, TF-IDF similarity, rule bonuses | `matches/matching.py` |
| Match reasons | Rules (no LLM) | `matches/matching.py` |

## 1. Plain summaries

### Steps

1. **Get the text.** Use the posting text from SAM.gov. If only a link is stored, fetch it with one SAM.gov
   API call, but only when allowed and when more than 2 calls are left for the day.
2. **Clean it.**
   - Remove HTML.
   - Replace emails and phone numbers with `[email]` and `[phone]`, so no contact info is sent to the AI.
   - Keep the first 3,500 characters.
3. **Ask the model.** Send the facts (title, agency, place, trade, who can bid) and the text, with
   `temperature: 0`, JSON mode, and low reasoning effort.
4. **Check every value.**
   - Drop any sentence or item with a number that isn't in the posting.
   - Keep a key date only if its numbers appear in the posting.
   - Due dates and places are never taken from the model. They come from the SAM.gov fields.
5. **Save it.** Each job is summarized once. The page loads the saved copy after that.

### Prompt rules (short version)

- Write for small trade business owners, many of them not native English speakers.
- 5th to 6th grade reading level. Short sentences, common words, no legal words.
- Only use facts from the posting. No phone numbers, emails, or names.
- Reply with one JSON object: `summary`, `job`, `requirements`, `skills`, `key_dates`.

The full prompt is `SYSTEM_PROMPT` in `summaries/ai.py`.

### Fallback

If there's no key, Groq fails, the reply isn't JSON, or the summary fails the checks, a **simple summary** is
built from the SAM.gov fields. For example: "Dept of the Army needs roofing in Peoria, IL. The job is: Roof
Replacement, Building 12. Only small businesses can bid." The page labels it as a basic summary.

### Limits and logging

- 20 AI summaries per hour per visitor. After that, visitors get the simple summary.
- The `summarize` command waits 3 seconds between calls. When Groq is busy, it waits 30 seconds and retries once.
- Every call is saved in `AIRequestLog`: feature, model, tokens in and out, speed in ms, and any error.
- Each summary stores a Flesch-Kincaid reading grade.

### Results so far (Nov 18)

| Measure | Value |
|---|---|
| Successful calls | 35 |
| Average speed | 475 ms |
| Average tokens | 740 in, 174 out |
| Average reading grade (32 AI summaries) | 6.2 |

## 2. My matches

### Steps

1. **Hard filters.** The job is open, it's in one of the user's states, and the user can bid on it. The
   set-aside must fit them (small business, 8(a), HUBZone, veteran-owned, woman-owned).
2. **Similarity.**
   - Compare the profile (trade names and services) with each job: title, trade, AI summary, skills, and
     the start of the posting.
   - Uses TF-IDF with single words and two-word phrases, and cosine similarity.
3. **Score** = 0.6 x similarity, plus these bonuses:
   - +0.30 if the job's industry code matches the user's trade
   - +0.05 if the job is set aside for a group
   - +0.05 if there are 7 or more days to bid
4. **Keep** the top 50 jobs with a score of at least 0.08 that either match the trade or share words with the profile.
5. **Reason.** One rule-based sentence, like "Your kind of work in Peoria, IL. Only for small businesses."
   or "Needs roofing and gutters, in Illinois. 14 days to bid."

### Planned upgrade

- Use sentence embeddings (`sentence-transformers/all-MiniLM-L6-v2`), computed once on my PC and stored in
  the database.

- The server only does the cosine math with NumPy, since PyTorch is too big for the free host. TF-IDF stays
  as the fallback.

## 3. Evaluation (for the final)

- **Matching.** 5 to 10 test profiles, each with hand-labeled top 10 matches. Report precision at 5 and at 10
  for embeddings, TF-IDF, and plain keyword search.

- **Summaries.** 5 test postings scored 1 to 10 for quality, with speed. Also check the right job, place,
  and dates, plus reading level.

- **Failure cases.** At least 2, with what went wrong and what was changed.
- **Cost.** Groq compared with running a model on a local GPU, using the token counts in `AIRequestLog`.
