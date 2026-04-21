"""Orchestrator - Master pipeline coordinator with hybrid parallel/sequential batch processing."""

import asyncio
import logging

from agents.gemini_agent import GeminiAgent
from agents.claude_agent import ClaudeAgent
from agents.chatgpt_agent import ChatGPTAgent
from services.scraper import JobScraper
from services.sheets_service import SheetsService
from services.latex_compiler import compile_latex_to_pdf

logger = logging.getLogger("resume_agent")


class Orchestrator:
    def __init__(self):
        self.gemini = GeminiAgent()
        self.claude = ClaudeAgent()
        self.chatgpt = ChatGPTAgent()
        self.sheets = SheetsService()
        self.scraper = JobScraper()

    # --- Phase 1: Parallel scraping + extraction ---

    async def _extract_single(self, url: str, url_row: int,
                               additional_context: str = "",
                               approved: bool = False,
                               job_description: str = "") -> tuple:
        """Scrape one URL and extract JD. Runs in parallel with others.
        If job_description is provided (manual paste), skips scraping."""
        try:
            if job_description:
                logger.info(f"  📋 Using manually provided JD for: {url[:80]}...")
                jd = await self.gemini.extract_job_description(job_description)
            else:
                logger.info(f"  📡 Scraping: {url[:80]}...")
                page_text = await self.scraper.scrape(url)
                jd = await self.gemini.extract_job_description(page_text)
            return (url, url_row, jd, additional_context, approved, None)
        except Exception as e:
            return (url, url_row, None, additional_context, approved, str(e))

    async def _parallel_extract(self, pending: list) -> list:
        """Phase 1: Scrape + extract ALL URLs concurrently."""
        logger.info(f"🚀 Phase 1: Extracting {len(pending)} job descriptions in parallel...")
        tasks = [
            self._extract_single(
                job["url"], job["row"],
                job.get("additional_context", ""),
                job.get("approved", False),
                job.get("job_description", "")
            )
            for job in pending
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        extracted = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"❌ Extraction failed: {result}")
                continue
            url, url_row, jd, additional_context, approved, error = result
            if error:
                self.sheets.update_url_status(
                    url_row, "Failed", f"Extraction error: {error[:200]}"
                )
                logger.error(f"❌ {url[:60]}: {error[:100]}")
            else:
                extracted.append((url, url_row, jd, additional_context, approved))
                logger.info(f"✅ Extracted: {jd.job_title} at {jd.company}")

        return extracted

    # --- Phases 2-5: Sequential per job (for Claude cache hits) ---

    async def _process_single_job(self, url: str, url_row: int, jd,
                                   additional_context: str = "",
                                   approved: bool = False) -> str | None:
        """Phases 2-5 for one job. Runs SEQUENTIALLY to maximize cache reuse.
        Returns 'pending_review' if role needs user review, None otherwise."""
        try:
            # Safety Check: Visa Sponsorship (Constraint #16)
            if jd.visa_sponsorship == False:
                reason = f"No H1B visa sponsorship for {jd.job_title} at {jd.company}"
                logger.warning(f"⚠️ {reason}")
                self.sheets.update_url_status(url_row, "Skipped", reason)
                return None

            # Safety Check: Role Appropriateness (Constraint #17)
            # NON-BLOCKING: flag for review, skip, continue with other jobs
            # Skip if user already approved this job manually
            if not approved and not jd.is_role_appropriate:
                reason = (f"{jd.job_title} at {jd.company}: "
                         f"{jd.role_appropriateness_reason}")
                logger.warning(f"⏸️ PAUSED: {reason}")
                self.sheets.update_url_status(
                    url_row, "Pending Review",
                    f"Role fit concern: {jd.role_appropriateness_reason}"
                )
                return "pending_review"

            # Phase 2: Tailor Resume (Claude 4.6 - cached system prompt)
            logger.info(f"✍️ Tailoring resume for {jd.job_title} at {jd.company}")
            draft_latex = await self.claude.tailor_resume(jd, additional_context)

            # Phase 3: Brutal Review (GPT-5.4 Nano)
            logger.info(f"🔍 Brutal review in progress...")
            review = await self.chatgpt.review_resume(draft_latex, jd)
            logger.info(
                f"📊 ATS: {review.overall_ats_score}/100 | "
                f"Verdict: {review.recommendation} | "
                f"Gaps: {len(review.critical_gaps)} | "
                f"Suggestions: {len(review.suggestions)}"
            )

            # Phase 4: Refine (Claude 4.6 - cached system prompt)
            # Pass FULL review (gaps + reality check + suggestions)
            logger.info(f"🔧 Claude evaluating {len(review.suggestions)} suggestions "
                       f"and {len(review.critical_gaps)} critical gaps...")
            final_latex = await self.claude.refine_resume(draft_latex, review)

            # Phase 4.5: Final ATS score on refined resume
            logger.info(f"🎯 Final ATS scoring...")
            final_score = await self.chatgpt.score_final_resume(final_latex, jd)
            logger.info(
                f"📊 Final ATS: {final_score.overall_ats_score}/100 | "
                f"Verdict: {final_score.recommendation} "
                f"(was {review.overall_ats_score}/100 before refinement)"
            )

            # Phase 5: Auto-compile PDF (enforce 2-page limit)
            logger.info(f"📄 Compiling PDF...")
            pdf_path, page_count = compile_latex_to_pdf(
                final_latex, jd.company, jd.job_title
            )
            if page_count > 2:
                logger.warning(f"⚠️ Resume is {page_count} pages — trimming to 2...")
                final_latex = await self.claude.trim_resume(final_latex, page_count)
                pdf_path, page_count = compile_latex_to_pdf(
                    final_latex, jd.company, jd.job_title
                )
                if page_count > 2:
                    logger.warning(f"⚠️ Still {page_count} pages after trim — proceeding anyway")

            # Update both sheets
            self.sheets.update_url_status(url_row, "Completed", "")
            self.sheets.append_to_tracker({
                "company": jd.company,
                "job_title": jd.job_title,
                "location": jd.location,
                "pdf_path": pdf_path
            })

            logger.info(f"✅ Done: {pdf_path}")
            return None

        except Exception as e:
            reason = f"Pipeline error: {str(e)[:200]}"
            logger.error(f"❌ Failed for {url[:60]}: {reason}")
            self.sheets.update_url_status(url_row, "Failed", reason)
            return None

    # --- Main entry points ---

    async def process_single(self, url: str, url_row: int = None):
        """Process a single URL end-to-end."""
        page_text = await self.scraper.scrape(url)
        jd = await self.gemini.extract_job_description(page_text)
        await self._process_single_job(url, url_row, jd)

    async def run_batch(self):
        """Process all pending URLs using hybrid parallel/sequential strategy."""
        pending = self.sheets.get_pending_urls()
        logger.info(f"📋 Found {len(pending)} pending jobs")

        if not pending:
            logger.info("No pending jobs found. Add URLs to your URL Sheet.")
            return

        # PHASE 1: Parallel - scrape + extract all JDs concurrently
        extracted = await self._parallel_extract(pending)
        logger.info(
            f"\n📊 Extraction complete: {len(extracted)}/{len(pending)} succeeded\n"
        )

        # PHASES 2-5: Sequential - tailor + review + refine + compile one at a time
        # This maximizes Claude prompt cache hits (90% cheaper on 2nd+ calls)
        flagged_for_review = []
        completed = 0

        for i, (url, url_row, jd, additional_context, approved) in enumerate(extracted):
            logger.info(f"\n{'='*50}")
            logger.info(
                f"Processing {i+1}/{len(extracted)}: {jd.job_title} at {jd.company}"
            )
            if approved:
                logger.info(f"✅ User-approved: skipping fit check")
            if additional_context:
                logger.info(f"📝 Additional context: {additional_context[:80]}...")

            result = await self._process_single_job(
                url, url_row, jd, additional_context, approved
            )

            if result == "pending_review":
                flagged_for_review.append({
                    "job": f"{jd.job_title} at {jd.company}",
                    "reason": jd.role_appropriateness_reason,
                    "url": url
                })
            else:
                completed += 1

        # --- End-of-batch summary ---
        logger.info(f"\n{'='*50}")
        logger.info(f"🎉 Batch complete: {completed} resumes generated")

        if flagged_for_review:
            logger.info(
                f"\n⏸️ {len(flagged_for_review)} jobs PAUSED for your review:"
            )
            for j, flag in enumerate(flagged_for_review, 1):
                logger.info(f"   {j}. {flag['job']}")
                logger.info(f"      Reason: {flag['reason']}")
                logger.info(f"      URL: {flag['url']}")
            logger.info(f"\n📝 To process these: review in your URL Sheet,")
            logger.info(f"   set Status to 'Approved' for approved jobs.")
            logger.info(f"   If scraping failed, paste the JD into column E (Job Description),")
            logger.info(f"   set Status to 'Approved', then run: python main.py --batch")
