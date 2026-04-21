# Resume Agent

A multi-agent pipeline that reads job URLs from a Google Sheet, tailors your LaTeX resume for each role using three LLMs, reviews it with a brutal ATS scorer, and compiles a PDF — automatically.

## Pipeline

```
Google Sheet (URLs)
       ↓
  Gemini 2.5 Flash  →  Extract structured job description
       ↓
  Claude Sonnet     →  Tailor resume to JD
       ↓
  GPT (review)      →  ATS score + gaps + suggestions
       ↓
  Claude Sonnet     →  Refine resume based on feedback
       ↓
  GPT (re-score)    →  Final ATS score
       ↓
  pdflatex          →  Compile PDF (2-page limit enforced)
       ↓
  Google Sheet      →  Update status + log to Job Tracker
```

Handles JS-rendered job pages (Playwright fallback), auto-skips roles without H1B sponsorship, flags questionable fit for manual review, and enforces a 2-page PDF limit with an automatic trim step.

## Requirements

- Python 3.11+
- [MiKTeX](https://miktex.org/) (Windows) or TeX Live (macOS/Linux) for PDF compilation
- API keys: Anthropic, OpenAI, Google Gemini
- Google Cloud service account with Sheets API enabled

## Setup

### 1. Clone and install

```bash
git clone https://github.com/hunainshahzad/resume-agent.git
cd resume-agent
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in your API keys and Google Sheet IDs:

```env
GEMINI_API_KEY=your_key
ANTHROPIC_API_KEY=your_key
OPENAI_API_KEY=your_key

URL_SHEET_ID=your_google_sheet_id
TRACKER_SHEET_ID=your_google_sheet_id

# Path to pdflatex binary
# Windows: C:\Users\<you>\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe
# macOS/Linux: pdflatex
PDFLATEX_PATH=pdflatex
```

### 3. Google Sheets setup

Create a Google Cloud service account and download the credentials JSON to `config/credentials.json`. Share both sheets with the service account email.

**URL Sheet columns** (Sheet 1):

| A | B | C | D | E |
|---|---|---|---|---|
| URL | Additional Context | Status | Reason | Job Description |

- Leave **Status** blank for new jobs to process
- Set **Status** to `Approved` to override the role fit check
- If scraping fails, paste the job description into column **E**, set Status to `Approved`, and re-run

**Job Tracker Sheet** — output only, the agent appends completed jobs automatically.

### 4. Configure your prompts

Copy all four example files and fill them in with your own content:

```bash
cp config/prompts/system_prompt.txt.example    config/prompts/system_prompt.txt
cp config/prompts/candidate_profile.txt.example config/prompts/candidate_profile.txt
cp config/prompts/reviewer_prompt.txt.example  config/prompts/reviewer_prompt.txt
cp config/prompts/tailoring_reminders.txt.example config/prompts/tailoring_reminders.txt
```

**`system_prompt.txt`** — The system prompt sent to Claude. Should contain:
- Your full base resume as LaTeX
- Instructions for how to tailor it (what to prioritize, what to never change, etc.)

**`candidate_profile.txt`** — 2-3 sentences describing your background. Used by Gemini to evaluate whether a role is appropriate for you. Example:
```
MS Computer Science student with 3 years of software engineering experience in
Python, Go, and distributed systems. Seeking Summer 2025 SWE internships in backend
or infrastructure roles. Flag as inappropriate only if the role has no engineering work.
```

**`reviewer_prompt.txt`** — The system prompt for the GPT reviewer. Write instructions for how you want your resume reviewed — how strict, what formatting rules to enforce, what verdict options to use.

**`tailoring_reminders.txt`** — Bullet-point constraints appended to every Claude tailoring request. Use `{job_title}` as a placeholder. Example:
```
- Never claim skills not present in the base resume
- End the summary with: 'seeking a Summer 2025 {job_title} internship to...'
- NEVER use em-dashes or en-dashes
- Keep all \href{} links intact
```

### 5. Add your resume

Place your base resume LaTeX file at `data/base_resume.tex`. This is gitignored — it stays local.

## Usage

Process all pending URLs from your sheet:
```bash
python main.py --batch
```

Process a single URL:
```bash
python main.py --url "https://jobs.example.com/posting/123"
```

Verbose logging:
```bash
python main.py --batch --verbose
```

## How the status column works

| Status | Meaning |
|--------|---------|
| *(blank)* | Pending — will be processed on next run |
| `Approved` | User-approved — skips fit check, uses manual JD in col E if provided |
| `Completed` | Done — PDF generated and logged to tracker |
| `Skipped` | Auto-skipped (e.g. no H1B sponsorship) |
| `Pending Review` | Flagged for manual review — role fit concern |
| `Failed` | Pipeline error — check the Reason column |

## Output

Generated PDFs are saved to `data/output/` as `Your Name Company Job Title.pdf`.

## Models used

| Agent | Model | Purpose |
|-------|-------|---------|
| Gemini | `gemini-2.5-flash` | JD extraction (structured output) |
| Claude | `claude-sonnet-4-6` | Resume tailoring + refinement |
| GPT | `gpt-5.4-nano` | ATS scoring + brutal review |

All models are configurable via `.env`.
