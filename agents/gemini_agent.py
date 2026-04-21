"""Gemini Agent - JD extraction via structured output."""

import asyncio
import logging
from google import genai
from google.genai import types
from google.genai.errors import ClientError

from config import settings
from models.schemas import JobDescription

logger = logging.getLogger("resume_agent")


class GeminiAgent:
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = settings.GEMINI_MODEL
        with open(settings.CANDIDATE_PROFILE_PATH, "r", encoding="utf-8") as f:
            self._candidate_profile = f.read().strip()

    async def extract_job_description(self, page_markdown: str) -> JobDescription:
        """Extract structured JD from raw page content using Gemini."""
        for attempt in range(5):
            try:
                return await self._extract(page_markdown)
            except ClientError as e:
                if e.code != 429:
                    raise
                wait = 10 * 2 ** attempt
                logger.warning(f"  ⏳ Gemini 429 rate limit — retrying in {wait}s (attempt {attempt + 1}/5)")
                await asyncio.sleep(wait)
        raise RuntimeError("Gemini rate limit exceeded after 5 retries")

    async def _extract(self, page_markdown: str) -> JobDescription:
        response = self.client.models.generate_content(
            model=self.model,
            contents=(
                "Extract the complete job description details from this page content. "
                "Pay special attention to whether the posting mentions visa sponsorship "
                "(H1B, work authorization, etc). If visa sponsorship is explicitly not "
                "offered, set visa_sponsorship=false. If not mentioned, set to null.\n\n"
                f"Also evaluate if this role is appropriate for a candidate with: "
                f"{self._candidate_profile}\n\n"
                f"PAGE CONTENT:\n{page_markdown}"
            ),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=JobDescription,
            ),
        )
        jd = JobDescription.model_validate_json(response.text)
        logger.info(f"  📋 Extracted: {jd.job_title} at {jd.company} ({jd.location})")
        return jd
