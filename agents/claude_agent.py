"""Claude Agent - Resume tailoring via Anthropic API."""

import logging

import anthropic

from config import settings
from models.schemas import JobDescription, ResumeReview

logger = logging.getLogger("resume_agent")


class ClaudeAgent:
    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = settings.CLAUDE_MODEL
        self._system_prompt = self._load_system_prompt()
        with open(settings.TAILORING_REMINDERS_PATH, "r", encoding="utf-8") as f:
            self._tailoring_reminders = f.read().strip()

    def _load_system_prompt(self) -> str:
        with open(settings.SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
            return f.read()

    async def _run_claude(self, user_msg: str) -> str:
        """Call Claude API with cached system prompt."""
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=settings.CLAUDE_MAX_TOKENS,
            system=[
                {
                    "type": "text",
                    "text": self._system_prompt,
                    "cache_control": {"type": "ephemeral"}
                }
            ],
            messages=[
                {"role": "user", "content": user_msg}
            ],
        )
        usage = response.usage
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_created = getattr(usage, "cache_creation_input_tokens", 0) or 0
        logger.debug(
            f"  tokens — input: {usage.input_tokens}, output: {usage.output_tokens}, "
            f"cache_read: {cache_read}, cache_created: {cache_created}"
        )
        return response.content[0].text

    def _strip_fences(self, text: str) -> str:
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[-1].strip() == "```":
                lines = lines[1:-1]
            else:
                lines = lines[1:]
            text = "\n".join(lines)
        return text

    def _clean_dashes(self, text: str) -> str:
        return (
            text.replace("\u2014", ",")
                .replace("\u2013", ",")
                .replace("--", " - ")
        )

    async def tailor_resume(self, jd: JobDescription,
                            additional_context: str = "") -> str:
        """First pass: Create tailored resume from JD."""
        user_msg = (
            f"Tailor my resume for this job. Output ONLY valid LaTeX code.\n\n"
            f"Job Details:\n{jd.model_dump_json(indent=2)}\n\n"
        )

        if additional_context:
            user_msg += (
                f"ADDITIONAL CONTEXT FROM CANDIDATE (incorporate naturally):\n"
                f"{additional_context}\n"
                f"Note: Weave this into relevant experience sections. Do not add "
                f"a new section for it. Make it sound like part of the original "
                f"experience, not an afterthought.\n\n"
            )

        reminders = self._tailoring_reminders.replace(
            "{job_title}", jd.job_title
        )
        user_msg += (
            f"Follow the 6-step analysis workflow in your instructions.\n"
            f"Steps 1-3: internal reasoning (analyze JD, review resume, gap analysis).\n"
            f"Steps 4-6: produce the final LaTeX output.\n\n"
            f"Key reminders:\n{reminders}"
        )

        latex = await self._run_claude(user_msg)
        latex = self._strip_fences(latex)
        latex = self._clean_dashes(latex)
        logger.info("  📊 Claude API: resume tailored")
        return latex

    async def trim_resume(self, latex: str, page_count: int) -> str:
        """Trim an oversized resume down to 2 pages."""
        user_msg = (
            f"This resume compiled to {page_count} pages but must fit in exactly 2 pages.\n\n"
            f"```latex\n{latex}\n```\n\n"
            f"Shorten it to fit in 2 pages using these strategies (in order of preference):\n"
            f"1. Remove the least relevant bullet points from experience sections\n"
            f"2. Tighten wordy bullet points (cut filler, keep impact)\n"
            f"3. Remove the weakest skills from the skills section\n"
            f"4. Reduce \\vspace or margin values slightly if still too long\n\n"
            f"CONSTRAINTS:\n"
            f"- Keep ALL section headers and job entries (do not remove entire roles)\n"
            f"- Keep at least 2 bullet points per experience entry\n"
            f"- Do NOT change contact info, education, or summary\n"
            f"- NEVER use -- or em-dashes or en-dashes\n"
            f"- Keep all \\href{{}} links intact\n\n"
            f"Output the trimmed LaTeX code ONLY."
        )
        latex = await self._run_claude(user_msg)
        latex = self._strip_fences(latex)
        latex = self._clean_dashes(latex)
        logger.info("  📊 Claude API: resume trimmed to fit 2 pages")
        return latex

    async def refine_resume(self, draft_latex: str,
                            review: ResumeReview) -> str:
        """Second pass: Incorporate GPT review feedback."""
        gaps_text = "\n".join([
            f"- GAP [{g.severity}]: {g.requirement} -> {g.candidate_status} "
            f"(fixable by rewording: {g.can_be_addressed_in_resume})"
            for g in review.critical_gaps
        ])

        suggestions_text = "\n".join([
            f"- [{s.priority}] Section: {s.section}\n"
            f"  Suggested: {s.suggested_text}\n"
            f"  Rationale: {s.rationale}"
            for s in review.suggestions
        ])

        user_msg = (
            f"Here is my draft resume:\n```latex\n{draft_latex}\n```\n\n"
            f"A brutal job fit reviewer assessed this resume:\n\n"
            f"ATS Score: {review.overall_ats_score}/100\n"
            f"Recommendation: {review.recommendation}\n"
            f"Reality Check: {review.reality_check}\n\n"
            f"Critical Gaps:\n{gaps_text}\n\n"
            f"Specific Suggestions:\n{suggestions_text}\n\n"
            f"YOUR TASK: Evaluate EACH suggestion and gap independently:\n"
            f"- ACCEPT suggestions marked 'critical' or 'important' if they "
            f"genuinely improve the resume and don't violate constraints\n"
            f"- ACCEPT gap fixes ONLY where can_be_addressed_in_resume=True\n"
            f"- REJECT suggestions that are generic, introduce dashes, "
            f"violate any constraint, or make the resume sound keyword-stuffed\n"
            f"- REJECT 'nice-to-have' suggestions unless they clearly add value\n"
            f"- IGNORE gaps where can_be_addressed_in_resume=False "
            f"(these are real experience gaps, not resume problems)\n\n"
            f"Output the final LaTeX resume code ONLY."
        )

        latex = await self._run_claude(user_msg)
        latex = self._strip_fences(latex)
        latex = self._clean_dashes(latex)
        logger.info("  📊 Claude API: resume refined")
        return latex
