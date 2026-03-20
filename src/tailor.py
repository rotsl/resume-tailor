"""
src/tailor.py
Multi-provider AI tailoring engine.
Supports:
  - Anthropic Claude  (any model string, e.g. claude-opus-4-5, claude-sonnet-4-6)
  - Google Gemini     (gemini-2.5-flash, gemini-2.5-flash-lite, gemini-2.5-pro)

Provider + model + API key are passed in at call time so the web UI can
accept them from the user. Falls back to environment variables for local/CLI use.
"""

import os
from pathlib import Path
from typing import Literal

PROVIDER = Literal["claude", "gemini"]


# ── Formatting instructions ───────────────────────────────────────────────────

def _load_instructions() -> str:
    instruct_path = Path(__file__).parent.parent / "instruct.md"
    if instruct_path.exists():
        return instruct_path.read_text(encoding="utf-8")
    return "Follow standard ATS-friendly resume and cover letter formatting."


# ── Prompt builders (shared across providers) ────────────────────────────────

def _resume_system_prompt(instructions: str) -> str:
    return f"""You are an expert resume writer and ATS optimization specialist.

FORMATTING INSTRUCTIONS (follow exactly):
{instructions}

ABSOLUTE RULES — NEVER VIOLATE:
1. You may ONLY use information that exists in the candidate's original resume.
2. Do NOT invent, embellish, or assume any experience, skills, metrics, or facts.
3. You MAY reorder, reword, and emphasize existing content to better match the job.
4. You MAY mirror keywords and phrases from the job description IF they accurately
   describe the candidate's existing experience.
5. If the candidate lacks a required skill, do NOT add it. Leave it absent.
6. Output ONLY the tailored resume text — no commentary, no preamble, no markdown fences."""


def _resume_user_prompt(resume_text: str, job_description: str, web_context: str) -> str:
    return f"""Tailor the following resume for the job description below.

=== ORIGINAL RESUME ===
{resume_text}

=== JOB DESCRIPTION ===
{job_description}

=== ADDITIONAL COMPANY/ROLE CONTEXT (for reference only) ===
{web_context or 'None available.'}

Instructions:
- Rewrite the resume to highlight the most relevant experience for this specific role.
- Use keywords from the job description where they truthfully apply to the candidate.
- Optimise for ATS parsing.
- Do NOT add any experience, skills, or achievements not present in the original resume.
- Output the full tailored resume text only."""


def _cover_system_prompt(instructions: str) -> str:
    return f"""You are an expert cover letter writer.

FORMATTING INSTRUCTIONS (follow exactly):
{instructions}

ABSOLUTE RULES — NEVER VIOLATE:
1. Only reference experience, achievements, and skills present in the candidate's resume.
2. Do NOT invent stories, metrics, or experiences.
3. Use the web context ONLY to reference the company's mission/values — do not fabricate
   insider knowledge.
4. Output ONLY the cover letter text — no commentary, no preamble, no markdown fences."""


def _cover_user_prompt(
    resume_text: str, job_description: str, tailored_resume: str, web_context: str
) -> str:
    return f"""Write a tailored cover letter for the following job using only the
candidate's actual experience from their resume.

=== ORIGINAL RESUME ===
{resume_text}

=== TAILORED RESUME (highlights to emphasise) ===
{tailored_resume}

=== JOB DESCRIPTION ===
{job_description}

=== COMPANY/ROLE CONTEXT (use for company references only) ===
{web_context or 'None available.'}

Instructions:
- Write a compelling, professional cover letter for this specific role.
- Reference real experience from the resume that matches the job requirements.
- Keep to 1 page / 4 paragraphs as per formatting instructions.
- Do NOT fabricate any experience, metrics, or claims.
- Output the cover letter text only."""


# ── Claude caller ─────────────────────────────────────────────────────────────

def _call_claude(
    system: str,
    user: str,
    api_key: str,
    model: str,
    max_tokens: int = 4096,
) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return message.content[0].text.strip()


# ── Gemini caller ─────────────────────────────────────────────────────────────

def _call_gemini(
    system: str,
    user: str,
    api_key: str,
    model: str,
    max_tokens: int = 4096,
) -> str:
    """
    Calls Gemini via the google-generativeai SDK.
    System prompt is prepended to the user message since Gemini's
    generateContent supports system_instruction natively in newer SDK versions.
    """
    try:
        import google.generativeai as genai
    except ImportError:
        raise ImportError(
            "google-generativeai is not installed. "
            "Run: pip install google-generativeai"
        )

    genai.configure(api_key=api_key)

    generation_config = genai.GenerationConfig(max_output_tokens=max_tokens)

    gemini_model = genai.GenerativeModel(
        model_name=model,
        system_instruction=system,
        generation_config=generation_config,
    )

    response = gemini_model.generate_content(user)
    return response.text.strip()


# ── Unified dispatcher ────────────────────────────────────────────────────────

def _call_ai(
    system: str,
    user: str,
    provider: str,
    model: str,
    api_key: str,
    max_tokens: int = 4096,
) -> str:
    if provider == "claude":
        return _call_claude(system, user, api_key, model, max_tokens)
    elif provider == "gemini":
        return _call_gemini(system, user, api_key, model, max_tokens)
    else:
        raise ValueError(f"Unknown provider: {provider!r}. Use 'claude' or 'gemini'.")


# ── Public API ────────────────────────────────────────────────────────────────

def tailor_resume(
    resume_text: str,
    job_description: str,
    web_context: str = "",
    provider: str = "claude",
    model: str = "claude-opus-4-5",
    api_key: str = "",
) -> str:
    """
    Tailor the resume to the job description.
    Returns the tailored resume as plain text.

    provider: "claude" or "gemini"
    model:    e.g. "claude-opus-4-5", "claude-sonnet-4-6",
                   "gemini-2.5-flash", "gemini-2.5-flash-lite"
    api_key:  if blank, falls back to ANTHROPIC_API_KEY / GEMINI_API_KEY env vars
    """
    if not api_key:
        api_key = (
            os.environ.get("ANTHROPIC_API_KEY", "")
            if provider == "claude"
            else os.environ.get("GEMINI_API_KEY", "")
        )
    if not api_key:
        raise ValueError(
            f"No API key provided for {provider}. "
            "Pass api_key= or set the environment variable."
        )

    instructions = _load_instructions()
    system = _resume_system_prompt(instructions)
    user = _resume_user_prompt(resume_text, job_description, web_context)
    return _call_ai(system, user, provider, model, api_key, max_tokens=4096)


def generate_cover_letter(
    resume_text: str,
    job_description: str,
    tailored_resume: str,
    web_context: str = "",
    provider: str = "claude",
    model: str = "claude-opus-4-5",
    api_key: str = "",
) -> str:
    """
    Generate a tailored cover letter.
    Returns the cover letter as plain text.
    """
    if not api_key:
        api_key = (
            os.environ.get("ANTHROPIC_API_KEY", "")
            if provider == "claude"
            else os.environ.get("GEMINI_API_KEY", "")
        )
    if not api_key:
        raise ValueError(
            f"No API key provided for {provider}. "
            "Pass api_key= or set the environment variable."
        )

    instructions = _load_instructions()
    system = _cover_system_prompt(instructions)
    user = _cover_user_prompt(resume_text, job_description, tailored_resume, web_context)
    return _call_ai(system, user, provider, model, api_key, max_tokens=2048)
