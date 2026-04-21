"""Job page scraper with httpx (fast) and Playwright (JS fallback)."""

import logging
import httpx
import html2text
from playwright.async_api import async_playwright

from config import settings

logger = logging.getLogger("resume_agent")


class JobScraper:
    def __init__(self):
        self.h2t = html2text.HTML2Text()
        self.h2t.ignore_links = False
        self.h2t.ignore_images = True
        self.h2t.ignore_emphasis = False
        self.h2t.body_width = 0  # No line wrapping

    async def scrape(self, url: str) -> str:
        """Scrape URL, falling back to Playwright for JS-rendered sites."""
        # Attempt 1: Fast HTTP fetch
        try:
            text = await self._fetch_httpx(url)
            if self._looks_like_job_page(text):
                logger.info(f"  📡 Scraped via httpx (fast path)")
                return text
        except Exception as e:
            logger.debug(f"  httpx failed: {e}")

        # Attempt 2: Playwright for JS-rendered pages
        logger.info(f"  🎭 Falling back to Playwright (JS-rendered site)")
        return await self._fetch_playwright(url)

    async def _fetch_httpx(self, url: str) -> str:
        """Fast HTTP fetch with html2text conversion."""
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=15,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                )
            }
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            markdown = self.h2t.handle(resp.text)
            return markdown[:settings.MAX_SCRAPE_CHARS]

    async def _fetch_playwright(self, url: str) -> str:
        """Playwright fetch for JS-rendered pages (LinkedIn, Greenhouse, etc)."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                html = await page.content()
            finally:
                await browser.close()
            markdown = self.h2t.handle(html)
            return markdown[:settings.MAX_SCRAPE_CHARS]

    def _looks_like_job_page(self, text: str) -> bool:
        """Check if the page actually has job content vs empty JS shell."""
        job_indicators = [
            "requirements", "qualifications", "responsibilities",
            "experience", "apply", "salary", "benefits",
            "about the role", "what you'll do", "who you are"
        ]
        text_lower = text.lower()
        matches = sum(1 for kw in job_indicators if kw in text_lower)
        return matches >= 3
