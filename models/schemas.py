"""Pydantic models for structured LLM output."""

from pydantic import BaseModel, Field


class JobDescription(BaseModel):
    """Structured job description extracted by Gemini."""
    job_title: str
    company: str
    location: str
    visa_sponsorship: bool | None = Field(
        default=None,
        description="Whether the job offers H1B visa sponsorship. "
                    "None if not mentioned."
    )
    experience_level: str
    key_requirements: list[str]
    preferred_qualifications: list[str]
    key_skills: list[str]
    responsibilities: list[str]
    salary_range: str | None = None
    is_role_appropriate: bool = Field(
        description="Whether the role is appropriate for a candidate with "
                    "data science, analytics, and BI background seeking "
                    "analytics/DS internships"
    )
    role_appropriateness_reason: str = Field(
        description="Why the role is or is not appropriate"
    )
    full_description_text: str = Field(
        description="The complete job description text for downstream agents"
    )


class RevisionSuggestion(BaseModel):
    """A single actionable suggestion from the reviewer."""
    section: str  # e.g., "Professional Summary", "Experience > Assurety"
    current_text: str
    suggested_text: str
    rationale: str
    priority: str = Field(
        description="'critical', 'important', or 'nice-to-have'"
    )


class CriticalGap(BaseModel):
    """A specific mismatch between resume and JD requirements."""
    requirement: str  # What the JD requires
    candidate_status: str  # What the candidate has (or doesn't)
    severity: str = Field(
        description="'dealbreaker', 'significant', or 'minor'"
    )
    can_be_addressed_in_resume: bool = Field(
        description="Can rewording fix it, or is it a real experience gap?"
    )


class ResumeReview(BaseModel):
    """Structured review output from the brutal reviewer (GPT-5.4 Nano)."""
    overall_ats_score: int = Field(ge=0, le=100)

    # Brutally Honest Assessment
    critical_gaps: list[CriticalGap] = Field(
        description="Major mismatches between resume and JD requirements. "
                    "Be specific: what's missing and how bad is it?"
    )
    reality_check: str = Field(
        description="Honest assessment of interview chances and competitive "
                    "position. No sugar-coating. Include estimated percentile "
                    "ranking among likely applicants."
    )
    recommendation: str = Field(
        description="One of: 'APPLY - Strong Match', 'APPLY - Competitive', "
                    "'APPLY WITH CAVEATS', 'UPSKILL FIRST', or 'LOOK ELSEWHERE'"
    )
    recommendation_reasoning: str = Field(
        description="2-3 sentences explaining the recommendation"
    )

    # Specific Improvements
    strengths: list[str]  # What's working well
    weaknesses: list[str]  # What's hurting the resume
    keyword_gaps: list[str]  # Missing ATS keywords from JD
    suggestions: list[RevisionSuggestion]  # Actionable fixes
    dash_violations: list[str] = Field(
        default_factory=list,
        description="Any instances of em-dashes, en-dashes, or -- found"
    )
