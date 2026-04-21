"""Central configuration with environment variable loading."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# --- API Keys ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- Model Selection (easy to swap) ---
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
CHATGPT_MODEL = os.getenv("CHATGPT_MODEL", "gpt-5.4-nano")

# --- Google Sheets ---
GOOGLE_CREDENTIALS_PATH = PROJECT_ROOT / os.getenv("GOOGLE_CREDENTIALS_PATH", "config/credentials.json")
URL_SHEET_ID = os.getenv("URL_SHEET_ID")
TRACKER_SHEET_ID = os.getenv("TRACKER_SHEET_ID")

# --- File Paths ---
BASE_RESUME_PATH = PROJECT_ROOT / "data" / "base_resume.tex"
OUTPUT_DIR = PROJECT_ROOT / "data" / "output"
CACHE_DIR = PROJECT_ROOT / "data" / "cache"
PROMPTS_DIR = PROJECT_ROOT / "config" / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system_prompt.txt"
CANDIDATE_PROFILE_PATH = PROMPTS_DIR / "candidate_profile.txt"
REVIEWER_PROMPT_PATH = PROMPTS_DIR / "reviewer_prompt.txt"
TAILORING_REMINDERS_PATH = PROMPTS_DIR / "tailoring_reminders.txt"

# --- LaTeX Compiler ---
# Set PDFLATEX_PATH in .env to override. Defaults to 'pdflatex' (must be on PATH).
PDFLATEX_PATH = os.getenv("PDFLATEX_PATH", "pdflatex")

# --- Token Budget Limits ---
MAX_SCRAPE_CHARS = 15000  # Truncate scraped content
CLAUDE_MAX_TOKENS = 8000  # Max output tokens for Claude
GPT_MAX_TOKENS = 4000     # Max output tokens for GPT review

# --- Ensure output directories exist ---
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
