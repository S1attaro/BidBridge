# BidBridge

Find government work you can win.

BidBridge shows every open federal contract from SAM.gov in one place, with clear search,
plain summaries, and matches for small local contractors (roofing, HVAC, cleaning, lawn care,
small IT shops, and more).

INFO 490, Project 2. Connor Slattery (cslat@illinois.edu).

## What works now

| Part | Status |
|---|---|
| Sign up, log in, log out | Working |
| Import the SAM.gov nightly CSV (`import_extract`) | Working |
| Daily updates from the SAM.gov API (`fetch_new`), with a daily call cap | Working |
| One-step automatic refresh (`refresh_jobs`): download, load, top up, close old jobs | Working |
| Job alert emails with new matching jobs, sent after each refresh, one-click stop link | Working |
| Due-date bands (closes today, this week, next week, later), a few jobs per band on the overview | Working |
| Sizes scale with the screen, from phones to large monitors | Working |
| Browse with search, type of work, state, who can bid, due date, and sort | Working |
| Contract page with quick facts, full posting, and SAM.gov link | Working |
| JSON API (`/api/contracts/`) | Working |
| Plain AI summaries (Groq), with checks and a no-AI fallback | Working |
| Profile (3 short steps) and My Matches with a reason for each job | Working (keyword matching) |
| Saved contracts with status and notes | Working |
| Map of open jobs by state, with a searchable state list | Working |
| Jobs grouped and colored by days left, details in a side panel | Working |
| Distance from your business, and "You can bid" from your profile | Working |
| Count of "Bid on SAM.gov" clicks | Working |
| Embedding matching (MiniLM) | Next |
| Dashboard and CSV download | Next |

## Setup (Windows)

Double-click `setup.bat`. It makes the virtual environment, installs packages, creates `.env`,
sets up the database, adds demo contracts, and runs the tests.

Then double-click `run.bat` and the site opens at http://127.0.0.1:8000.

Same steps by hand:

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

## Environment variables (`.env`)

| Name | What it is |
|---|---|
| `DJANGO_SECRET_KEY` | Any long random string. Required when `DJANGO_DEBUG=False`. |
| `DJANGO_DEBUG` | `True` on your computer, `False` on the server. |
| `DJANGO_ALLOWED_HOSTS` | Comma list, like `127.0.0.1,localhost` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | The site address on the server, like `https://name.pythonanywhere.com` |
| `SAM_API_KEY` | Free key from SAM.gov (Account Details > Public API Key) |
| `SAM_DAILY_CALL_CAP` | Stop after this many SAM.gov calls a day. Default 8. |
| `GROQ_API_KEY` | Free key from https://console.groq.com/keys |
| `GROQ_MODEL` | Default `openai/gpt-oss-20b` |

## Data

**Keeping jobs up to date (automatic).** One command does it all:

```
python manage.py refresh_jobs
```

It downloads SAM.gov's free nightly file of every notice (no key and no call limit), loads
the open jobs, closes ones past due, then uses the API to add anything posted since. If the
file is less than 20 hours old it skips the download. If the download fails it keeps the old
file, or loads the last 30 days from the API instead. Double-click `update_jobs.bat` to run it,
or add that file to Windows Task Scheduler to run every morning.

**Job alerts.** Users turn on "Email me new jobs that fit" in step 3 of their profile.
`refresh_jobs` runs `send_alerts` at the end, which emails each of them the new jobs (up to 10)
that fit their profile. Jobs closing in under 2 days are left out. With no `EMAIL_HOST` in
`.env`, the emails print in the terminal so you can test without sending anything. To really
send them, fill in the email lines in `.env` (see `.env.example`).

**Nightly CSV (by hand).** You can also download `ContractOpportunitiesFullCSV.csv` from
https://sam.gov/data-services (Contract Opportunities > datagov), put it in `data/raw/`, and run:

```
python manage.py import_extract data\raw\ContractOpportunitiesFullCSV.csv --show-header
python manage.py import_extract data\raw\ContractOpportunitiesFullCSV.csv
python manage.py import_extract data\raw\ContractOpportunitiesFullCSV.csv --states IL,IN,WI,MO,IA
```

Only open notices (solicitations, combined solicitations, presolicitations, and sources
sought) with a due date in the future are kept. Running it again updates rows instead of
adding copies.

**API (daily updates).** Needs `SAM_API_KEY`. Each call returns up to 1,000 notices.

```
python manage.py fetch_new --days 2
```

Every call is saved in the `ApiCall` table. The command stops at `SAM_DAILY_CALL_CAP`.

**Map points.** Each contract gets a map point from its ZIP code (or city and state) when it's
imported. For contracts loaded before this existed, run:

```
python manage.py geocode
```

ZIP locations come from `data/zips.csv` (built from the free `zipcodes` package). State shapes in
`static/data/us-states.json` come from the `us-atlas` package (U.S. Census boundaries).

**Demo data.** `python manage.py seed_demo` adds 30 made-up contracts, labeled "Demo".
`python manage.py seed_demo --clear` removes them.

## AI features

**Plain summaries.** Open any contract page and the summary loads by itself. To make
summaries ahead of time (faster pages, good for a demo):

```
python manage.py summarize --limit 20 --state IL
python manage.py summarize --limit 20 --trade roofing --fetch-text
```

`--fetch-text` gets missing posting text from SAM.gov (one call per contract, and it always
leaves 2 calls for the daily update). Without `GROQ_API_KEY`, or when Groq fails, a simple
summary is made from the SAM.gov fields instead. Each AI call is logged in `AIRequestLog`
(speed and tokens).

**My Matches.** Sign up, fill in the profile, and the matches page lists the best open jobs
with a one-sentence reason. Matching uses hard filters (state, who can bid, open), text
similarity, and small bonuses (same trade code, set-aside, time left).

## JSON API

```
GET /api/contracts/?q=roof&state=IL&trade=roofing&set_aside=small&due_within=30&sort=due&limit=20&offset=0
GET /api/contracts/<notice_id>/
```

`trade` uses the keys in `contracts/codes.py` (like `roofing`, `janitorial`, `landscaping`).
`set_aside` is one of `small`, `8a`, `hubzone`, `sdvosb`, `vosb`, `wosb`, `none`.

## Apps

| App | What it holds |
|---|---|
| `core` | Home, sign up, about page, base template |
| `contracts` | Contract and Agency models, importer, browse, detail, JSON API, SAM.gov client |
| `summaries` | Groq client, summary checks, fallback, rate limit, AI request log |
| `matches` | Contractor profile, matching, My Matches page |
| `saved` | Saved contracts: save, status, notes, remove |

## Tests

```
python manage.py test
```
