"""ChatGPT Agent - Brutally Honest Job Fit Analyzer using GPT-5.4 Nano."""

import logging
import openai

from config import settings
from models.schemas import JobDescription, ResumeReview

logger = logging.getLogger("resume_agent")


class ChatGPTAgent:
    def __init__(self):
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.CHATGPT_MODEL
        with open(settings.REVIEWER_PROMPT_PATH, "r", encoding="utf-8") as f:
            self._reviewer_prompt = f.read().strip()

    async def review_resume(self, draft_latex: str,
                            jd: JobDescription) -> ResumeReview:
        """Brutally honest review of a tailored resume against the JD."""
        response = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=[{
                "role": "system",
                "content": self._reviewer_prompt
            }, {
                "role": "user",
                "content": (
                    f"CRITICALLY analyze this resume against the job description.\n\n"
                    f"JOB: {jd.job_title} at {jd.company} ({jd.location})\n"
                    f"Experience Level: {jd.experience_level}\n"
                    f"Requirements: {', '.join(jd.key_requirements[:10])}\n"
                    f"Key Skills: {', '.join(jd.key_skills[:10])}\n"
                    f"Responsibilities: {', '.join(jd.responsibilities[:8])}\n\n"
                    f"RESUME:\n```latex\n{draft_latex}\n```\n\n"
                    f"Provide your brutal assessment. Target: 90-95% ATS match.\n"
                    f"For each critical gap, specify if it can be fixed by rewording "
                    f"or if it represents a genuine experience gap."
                )
            }],
            response_format=ResumeReview,
        )
        review = response.choices[0].message.parsed
        logger.info(
            f"  💰 GPT review cost: "
            f"input={response.usage.prompt_tokens}, "
            f"output={response.usage.completion_tokens}"
        )
        return review

    async def score_final_resume(self, final_latex: str,
                                 jd: JobDescription) -> ResumeReview:
        """Re-evaluate the refined resume to get the final ATS score."""
        response = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=[{
                "role": "system",
                "content": self._reviewer_prompt
            }, {
                "role": "user",
                "content": (
                    f"This is the FINAL refined resume. Score it against the job description.\n"
                    f"Focus on ATS score and overall verdict — no need for detailed suggestions.\n\n"
                    f"JOB: {jd.job_title} at {jd.company} ({jd.location})\n"
                    f"Experience Level: {jd.experience_level}\n"
                    f"Requirements: {', '.join(jd.key_requirements[:10])}\n"
                    f"Key Skills: {', '.join(jd.key_skills[:10])}\n"
                    f"Responsibilities: {', '.join(jd.responsibilities[:8])}\n\n"
                    f"RESUME:\n```latex\n{final_latex}\n```\n\n"
                    f"Provide the final ATS score and verdict."
                )
            }],
            response_format=ResumeReview,
        )
        final_score = response.choices[0].message.parsed
        logger.info(
            f"  💰 GPT final score cost: "
            f"input={response.usage.prompt_tokens}, "
            f"output={response.usage.completion_tokens}"
        )
        return final_score
