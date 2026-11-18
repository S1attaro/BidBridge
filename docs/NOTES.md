# BidBridge Notes

Project notes so nothing gets lost. Setup steps are in the README.

## Run the site

```
cd "C:\Users\Connor\Documents\UIUC\Fall 2026\INFO 490\BidBridge\bidbridge"
.venv\Scripts\activate
python manage.py migrate
python manage.py runserver
```

Or double-click `run.bat`.

The job list refreshes every morning at 8:00 AM. The Windows Task Scheduler task "BidBridge refresh" runs `update_jobs.bat`. It only runs if the PC is on.

Tests: `python manage.py test`. The yellow WARNING lines during tests are expected. They come from tests that check bad requests and a down AI.

## Commands

| Command | What it does |
|---|---|
| `python manage.py refresh_jobs` | Main data update. Same as `update_jobs.bat`. |
| `python manage.py geocode` | Adds map points to old rows. |
| `python manage.py summarize --limit 30 --state IL` | Makes AI summaries ahead of time. |

## How the data works

- `refresh_jobs` downloads SAM.gov's free nightly CSV (no key, no call limit). It skips the download if the file is under 20 hours old.
- It loads open jobs, closes past-due ones, removes repeats, and tops up with the SAM.gov API. It keeps 2 API calls for AI summaries.
- Then it sends job alert emails.
- If the download fails, it uses the old file, or loads the last 30 days from the API.
- **Parts orders are hidden.** Product buys (numeric PSC codes, or "53--" style titles) are not on-site work.
- **Repeats are hidden.** Agencies repost a job each time they change it, and every copy gets a new notice ID. The copies share a solicitation number, so only the newest one shows.
- Example run (Nov 18): 11,802 loaded notices became 2,091 real, on-site jobs still open for bids.
- Map points come from ZIP or city using `data/zips.csv`.
- The SAM.gov API is capped at 8 calls a day (`SAM_DAILY_CALL_CAP`). Every call is logged in `ApiCall`.

## Short titles

Short titles come from `contracts/cleanup.py`, which is rule based.

- Removes product codes, solicitation numbers, fiscal years, acronyms in parentheses, notice words (RFQ, Sources Sought, Amendment), and contract jargon (IDIQ, BPA).
- Fixes ALL CAPS titles.
- Max 80 characters. It only cuts off locations, keeps at least 4 words, and never cuts at dashes or colons.
- When two jobs would end up with the same title, it adds a contract number or the solicitation number.
- The details panel shows the full official title under the short one.

## AI

- **Summaries:** Groq, `openai/gpt-oss-20b`, with JSON output.
  - Drops any number that isn't in the posting.
  - Removes emails and phone numbers before sending text to the AI.
  - Uses a simple summary if the AI fails.
  - Limit of 20 per hour per visitor. Every call is logged in `AIRequestLog`.
- **Matching:** hard filters first (state, can bid, still open). Then TF-IDF similarity plus bonuses, with a one-sentence reason per match.
- **Planned:** embedding matching (MiniLM, computed on a local PC), and a dashboard with CSV download and a bid-click chart.
- **Backup AI:** NCSA Lumen works with the same code. Set `AI_BASE_URL=https://lumen.ncsa.illinois.edu/v1` plus a Lumen key and model.

## Settings (`.env`, see `.env.example`)

| Setting | Notes |
|---|---|
| `DJANGO_SECRET_KEY` | |
| `DJANGO_DEBUG` | |
| `DJANGO_ALLOWED_HOSTS` | |
| `SAM_API_KEY` | |
| `SAM_DAILY_CALL_CAP` | 8 |
| `GROQ_API_KEY` | |
| `GROQ_MODEL` | `openai/gpt-oss-20b` |
| `AI_BASE_URL` | Blank means Groq |
| `SAM_EXTRACT_URL` | Blank means the default |
| `SITE_URL` | |
| `EMAIL_HOST` | Without it, emails print in the terminal |
| `EMAIL_HOST_USER` | |
| `EMAIL_HOST_PASSWORD` | |
| `DEFAULT_FROM_EMAIL` | |

For real emails, use a Gmail app password with `EMAIL_HOST=smtp.gmail.com`.

## Things that look like bugs but aren't

- **Few matches for some profiles.** Some trade and state mixes have very few open jobs, and some of those are only for 8(a) or veteran-owned businesses. For a demo, use more states or trades.
- **"Place not listed".** SAM.gov leaves the place blank on many jobs, mostly remote services and research.
- **Odd titles like "NGC".** The original SAM.gov title is just that.
- **Titles ending in a solicitation number.** That's how look-alike jobs are told apart.

## Still to do

- Deploy to PythonAnywhere (free plan).
  - Check whether `sam.gov` and `api.sam.gov` are on the free allowlist.
  - If they aren't, refresh on the PC and move the data with `dumpdata` and `loaddata`.
  - Don't install PyTorch on the server.
- Final (Dec 8):
  - 5-test eval table, 2 failure cases, and one before/after improvement
  - Cost comparison (Groq vs local GPU)
  - Plan for 10,000 users
  - Security notes
  - `README_AI.md`
  - 3-minute video
- Poster: present Dec 11, 9:00 to 11:30, Illini Union Rooms ABC.
