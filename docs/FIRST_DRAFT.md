# BidBridge: P2-A3 First Draft

**INFO 490, Project 2.** Connor Slattery (cslat@illinois.edu). Team TBD.

**Repo:** https://github.com/S1attaro/BidBridge

BidBridge is my solo Project 2, approved by Prof. Gupta after the RentCheck team split. See the email
thread "Question About Group Assignment – Rent Check" from Nov 16, 2026.

---

## 1. Scope update

**Product.** BidBridge, "Find government work you can win." A simpler way for small contractors to find
federal jobs on SAM.gov that fit their trade and that they are allowed to bid on.

**Problem.** The federal government posts thousands of contracts on SAM.gov, and it has goals to send part
of that money to small businesses. But many small local contractors never bid. SAM.gov is built for people
who already know the system. Its search depends on industry codes most owners have never heard of, and the
postings are long and full of government terms. Most of the list isn't even on-site work: of the 11,802 notices loaded on Nov 18, 7,458
were parts and supply orders.

**Target users.** Small trade businesses (roofing, HVAC, electrical, painting, landscaping, janitorial, small
IT shops), especially first-time federal bidders and owners who are not native English speakers.

**Core value.** Go from "what's out there?" to "Bid on SAM.gov" in a few clicks, with plain words at every step.

**Core features.**

1. **All open jobs in one place.** A US map and state list, jobs grouped by when they close, and filters for
   type of work, due date, and "only jobs I can bid on."
2. **Plain summaries (AI).** A short summary of each posting at a 5th to 6th grade reading level, with key
   dates and what a bidder needs.
3. **My matches (AI).** A 3-step profile (trades, states, certifications). The site ranks open jobs for that
   business and gives a one-sentence reason for each.

**Smaller features.** Saved jobs with status and notes, job alert emails, "Add to calendar," and a JSON API.
A dashboard with charts and a CSV download is planned for the final.

**Changes from RentCheck.** Project 2 started as RentCheck (Team 19). My partner stopped responding, and
Prof. Gupta approved splitting the group so I could do Project 2 alone with a new idea. RentCheck needed
students to report their own rent prices, which is hard to collect alone. BidBridge uses free public data
from SAM.gov, so one person can build and run it.

---

## 2. Django foundation (what works now)

**Main flow: input, database, result.**

| Step | What happens |
|---|---|
| Input | A contractor fills in the profile form: trades, states, ZIP, certifications, and alerts. |
| Database | `ContractorProfile` is saved. Matching reads open `Contract` rows and saves ranked `Match` rows. |
| Result | "My matches" lists the best jobs with a reason. Opening one shows the AI summary and a "Bid on SAM.gov" button. |

**Apps.**

| App | What it holds |
|---|---|
| `core` | Sign up, about page, base template |
| `contracts` | `Agency`, `Contract`, `BidClick`, `ApiCall` models. Importer, browse page, details panel, JSON API, SAM.gov client |
| `summaries` | `ContractSummary`, `AIRequestLog`. Groq client, value checks, fallback, rate limit |
| `matches` | `ContractorProfile`, `Match`. Profile form, matching, job alert emails |
| `saved` | `SavedContract`. Save, status, notes, remove |

**Models and relationships.**

- `Contract` belongs to an `Agency` (foreign key).
- `ContractSummary` is one-to-one with `Contract`.
- `ContractorProfile` is one-to-one with Django's `User`.
- `Match` links a `ContractorProfile` and a `Contract`, with a score and a reason.
- `SavedContract` links a `User` and a `Contract`, with a status and a note.
- `ApiCall`, `AIRequestLog`, and `BidClick` log outside calls, AI calls, and bid clicks.

**Views.** A mix of class-based and function-based views:

- Class-based: `ContractListView`, `ContractDetailView`, `SavedListView`, `SavedUpdateView`, `SavedDeleteView`.
- Function-based: sign up, profile, matches, save toggle, summary, calendar file, and the API.

**Forms.** `SignupForm`, `ProfileForm` (3 steps), `SavedContractForm`, and `ContractFilterForm`.

**Login rules.** Profiles, matches, and saved jobs need a login. Users only see their own. Anyone can browse jobs.

**Internal API.** `GET /api/contracts/` returns JSON, with search, filters, sorting, and paging.
`GET /api/contracts/<notice_id>/` returns one job.

**Outside data (SAM.gov).**

- `python manage.py refresh_jobs` downloads SAM.gov's free nightly file (no key or call limit) and loads
  the open jobs. Then it closes past-due jobs, tops up with the SAM.gov API, and sends job alerts.

- The API allows about 10 calls a day, so the app stops at 8 and logs every call in `ApiCall`.
- It runs every morning at 8:00 AM with Windows Task Scheduler.

**Data cleanup.** On Nov 18, 11,802 notices were loaded from the nightly file:

- 7,458 were parts and supply orders, so they are hidden.
- 2,001 were older copies of reposted jobs. Copies share a solicitation number, so only the newest one shows.
- 252 had a due date that already passed.
- That leaves **2,091 real, on-site jobs** still open for bids.

Long titles are shortened by rules (product codes, notice numbers, and contract jargon are removed), and the
full title is still shown on the details panel.

**Tests.** 146 tests, all passing. They cover the importer, cleanup, filters, views, login rules, the API call
cap, matching, summaries, and the fallback paths. Outside services are faked, so tests need no keys.

---

## 3. AI plan and working prototype

### 3a. Plain summaries (working)

| Part | Plan |
|---|---|
| Model | `openai/gpt-oss-20b` on Groq. The model name is in `.env`, so it is easy to swap. |
| Input | Up to 3,500 characters of the posting, plus the title, agency, place, trade, and who can bid. Emails and phone numbers are removed first. |
| Output | JSON: `summary`, `job`, `requirements`, `skills`, `key_dates`. |
| Checks | Any sentence or item with a number that isn't in the posting is dropped. Due dates and places always come from SAM.gov fields, never the model. |
| Fallback | If Groq is down, busy, or has no key, a simple summary is built from the SAM.gov fields. The page always works. |
| Limits | 20 AI summaries per hour per visitor. Each summary is saved, so a job is only summarized once. |
| Logging | Every call is saved in `AIRequestLog` with speed, tokens, and errors. |

**Results so far.** 35 successful calls averaged **475 ms**, about 740 tokens in and 174 tokens out. The 32
saved AI summaries average a **6.2 reading grade** (goal: 5 to 6).

**One problem found and fixed.** Making 30 summaries at once went over Groq's free rate limit after 11 calls.
The other 19 got simple summaries, so nothing broke, but they weren't the AI version. The `summarize` command
now waits between calls, retries once when Groq is busy, and has a `--fix-simple` option to redo the simple
ones. After the fix, all 19 were remade with AI.

### 3b. Matching (working, upgrade planned)

| Part | Now | Planned |
|---|---|---|
| Hard filters | Open, in the user's states, and a set-aside the user can bid on | Same |
| Ranking | TF-IDF similarity between the profile and each job | Sentence embeddings (`all-MiniLM-L6-v2`), computed on my PC and stored |
| Bonuses | Same trade code, set-aside made for them, 7+ days to bid | Add distance |
| Reason | One rule-based sentence ("Your kind of work in Peoria, IL. Only for small businesses.") | Same |

**Testing plan for the final.**

- Make 5 to 10 test profiles and hand-label whether each of the top 10 matches is a real fit. Report
  precision at 5 and at 10, and compare embeddings, TF-IDF, and plain keyword search.

- Check 10 summaries by hand for the right job, place, and dates, plus reading level and speed.

---

## 4. Roadmap

Dates for planned work are my target dates. The final is due Tue Dec 8, and the poster is presented Fri Dec 11.

| Task | Current status | Responsible | Expected completion |
|---|---|---|---|
| Django core features (browse, details, profile, matches, saved, alerts) | Done | Connor | Done |
| Database and APIs (SAM.gov import, daily refresh, JSON API, cleanup) | Done | Connor | Done |
| AI summaries (Groq, checks, fallback, rate limit) | Done | Connor | Done |
| AI matching upgrade (MiniLM embeddings) | Planned | Connor | Nov 29 |
| Dashboard (charts, CSV download, bid-click chart) | Planned | Connor | Nov 30 |
| Deployment (PythonAnywhere free plan) | Planned | Connor | Nov 30 |
| Evaluation (5-test table, failure cases, before and after, cost) | Planned | Connor | Dec 4 |
| Documentation (`README.md`, `README_AI.md`) | Started | Connor | Dec 6 |
| Final video and submission | Planned | Connor | Dec 8 |
| Poster | Planned | Connor | Dec 10 (presented Dec 11) |

---

## 5. Repo and README

- Repo: https://github.com/S1attaro/BidBridge
- `README.md` has setup steps, settings, data commands, the AI features, and the API.
- `README_AI.md` has the AI design. It will hold the evaluation for the final.
