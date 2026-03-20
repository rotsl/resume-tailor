"""
main.py
CLI entry point for the Resume Tailor system.
Supports job URL, job description text, and file uploads for both
job description and resume.

Usage:
  python main.py                         # Interactive wizard
  python main.py --help                  # Show all options
"""

import os
import sys
import typer
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint

load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.parser import extract_text
from src.web_context import fetch_company_context
from src.tailor import tailor_resume, generate_cover_letter
from src.pdf_generator import generate_resume_pdf, generate_cover_letter_pdf
from src.notion_integration import (
    log_job_to_notion,
    save_outputs_to_notion,
    read_job_from_notion_page,
    list_past_applications,
)

app = typer.Typer(help="🎯 Resume Tailor — AI-powered resume & cover letter tailoring")
console = Console()

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _validate_env():
    missing = []
    if not os.environ.get("ANTHROPIC_API_KEY"):
        missing.append("ANTHROPIC_API_KEY")
    if missing:
        console.print(
            f"[bold red]❌ Missing environment variables: {', '.join(missing)}[/]\n"
            "Copy .env.example to .env and fill in your keys.",
            style="red",
        )
        raise typer.Exit(1)


def _get_job_description(
    job_url: str = "",
    job_file: str = "",
    job_text: str = "",
    notion_page_id: str = "",
) -> tuple[str, str]:
    """Returns (job_description_text, job_url)."""
    if notion_page_id:
        console.print("📓 Reading job description from Notion page...")
        return read_job_from_notion_page(notion_page_id), ""

    if job_file:
        console.print(f"📄 Reading job description from file: {job_file}")
        return extract_text(job_file, Path(job_file).name), ""

    if job_url:
        import httpx, re
        console.print(f"🌐 Fetching job description from URL: {job_url}")
        try:
            resp = httpx.get(job_url, timeout=15, follow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0"})
            text = re.sub(r"<[^>]+>", " ", resp.text)
            text = re.sub(r"\s+", " ", text).strip()[:8000]
            return text, job_url
        except Exception as e:
            console.print(f"[yellow]⚠️  Could not fetch URL: {e}. Please paste the JD manually.[/]")

    if job_text:
        return job_text, ""

    # Interactive fallback
    console.print("\n[bold cyan]Paste the job description below.[/]")
    console.print("[dim]Enter a blank line followed by 'END' when done.[/]\n")
    lines = []
    while True:
        line = input()
        if line.strip().upper() == "END":
            break
        lines.append(line)
    return "\n".join(lines), ""


def _get_resume_text(resume_file: str = "", resume_text: str = "") -> str:
    if resume_file:
        console.print(f"📄 Reading resume from file: {resume_file}")
        return extract_text(resume_file, Path(resume_file).name)

    if resume_text:
        return resume_text

    console.print("\n[bold cyan]Paste your resume below.[/]")
    console.print("[dim]Enter a blank line followed by 'END' when done.[/]\n")
    lines = []
    while True:
        line = input()
        if line.strip().upper() == "END":
            break
        lines.append(line)
    return "\n".join(lines)


def _extract_company_job_title(job_description: str) -> tuple[str, str]:
    """Best-effort extraction of company and job title from JD text."""
    import re
    lines = job_description.split("\n")[:10]

    company = "Unknown Company"
    job_title = "Role"

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # First substantial line is likely the job title
        if job_title == "Role" and len(line) > 3:
            job_title = line[:80]
        # Look for "at Company" pattern
        match = re.search(r"\bat\s+([A-Z][A-Za-z0-9\s&,.]+?)(?:\s*[|–—,.]|$)", line)
        if match:
            company = match.group(1).strip()[:60]
            break

    return company, job_title


# ── Main Command ──────────────────────────────────────────────────────────────

@app.command()
def tailor(
    resume_file: Optional[str] = typer.Option(None, "--resume", "-r", help="Path to resume PDF/DOCX/TXT"),
    job_file: Optional[str] = typer.Option(None, "--job-file", "-jf", help="Path to job description PDF/DOCX/TXT"),
    job_url: Optional[str] = typer.Option(None, "--job-url", "-u", help="URL of the job posting"),
    notion_page: Optional[str] = typer.Option(None, "--notion-page", "-n", help="Notion page ID containing the job description"),
    output_name: Optional[str] = typer.Option(None, "--output", "-o", help="Base name for output files (no extension)"),
    no_notion: bool = typer.Option(False, "--no-notion", help="Skip saving to Notion"),
    skip_web: bool = typer.Option(False, "--skip-web", help="Skip web context fetching"),
):
    """
    🎯 Tailor your resume and generate a cover letter for a specific job.

    Outputs two PDFs: tailored_resume.pdf and cover_letter.pdf
    """
    console.print(Panel.fit(
        "[bold cyan]Resume Tailor[/] — Powered by Claude AI + Notion MCP",
        border_style="cyan"
    ))

    _validate_env()

    # ── Step 1: Collect inputs ────────────────────────────────────────────────
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  transient=True) as progress:

        task = progress.add_task("Loading job description...", total=None)
        job_desc, detected_url = _get_job_description(
            job_url=job_url or "",
            job_file=job_file or "",
            notion_page_id=notion_page or "",
        )
        if not job_desc.strip():
            console.print("[red]❌ Job description is empty. Aborting.[/]")
            raise typer.Exit(1)
        progress.update(task, description="✅ Job description loaded")

        task2 = progress.add_task("Loading resume...", total=None)
        resume = _get_resume_text(resume_file=resume_file or "")
        if not resume.strip():
            console.print("[red]❌ Resume is empty. Aborting.[/]")
            raise typer.Exit(1)
        progress.update(task2, description="✅ Resume loaded")

    company, job_title = _extract_company_job_title(job_desc)
    console.print(f"\n[bold]Detected role:[/] {job_title}")
    console.print(f"[bold]Detected company:[/] {company}\n")

    # ── Step 2: Web context ──────────────────────────────────────────────────
    web_context = ""
    if not skip_web:
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                      transient=True) as progress:
            task = progress.add_task("Fetching company context from web...", total=None)
            web_context = fetch_company_context(job_desc, detected_url or job_url or "")
            progress.update(task, description="✅ Web context fetched")

    # ── Step 3: Tailor resume ────────────────────────────────────────────────
    console.print("[bold cyan]Step 1/3:[/] Tailoring resume with Claude AI...")
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  transient=True) as progress:
        task = progress.add_task("Analysing and tailoring...", total=None)
        tailored = tailor_resume(resume, job_desc, web_context)
        progress.update(task, description="✅ Resume tailored")

    # ── Step 4: Generate cover letter ────────────────────────────────────────
    console.print("[bold cyan]Step 2/3:[/] Generating cover letter with Claude AI...")
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  transient=True) as progress:
        task = progress.add_task("Writing cover letter...", total=None)
        cover = generate_cover_letter(resume, job_desc, tailored, web_context)
        progress.update(task, description="✅ Cover letter generated")

    # ── Step 5: Generate PDFs ────────────────────────────────────────────────
    console.print("[bold cyan]Step 3/3:[/] Generating PDFs...")
    base = output_name or f"{company.replace(' ', '_')}_{job_title[:20].replace(' ', '_')}"
    resume_pdf_path = str(OUTPUT_DIR / f"{base}_resume.pdf")
    cover_pdf_path = str(OUTPUT_DIR / f"{base}_cover_letter.pdf")

    generate_resume_pdf(tailored, resume_pdf_path)
    generate_cover_letter_pdf(cover, cover_pdf_path)

    # ── Step 6: Save to Notion ───────────────────────────────────────────────
    notion_job_id = None
    if not no_notion and os.environ.get("NOTION_API_KEY"):
        console.print("📓 Saving to Notion...")
        notion_job_id = log_job_to_notion(job_title, company, job_desc[:500])
        save_outputs_to_notion(job_title, company, tailored, cover, notion_job_id)
        console.print("✅ Saved to Notion databases")

    # ── Done ─────────────────────────────────────────────────────────────────
    console.print(Panel(
        f"[bold green]✅ Done![/]\n\n"
        f"📄 Tailored Resume:  [cyan]{resume_pdf_path}[/]\n"
        f"✉️  Cover Letter:    [cyan]{cover_pdf_path}[/]",
        title="Output Files",
        border_style="green",
    ))


# ── History Command ───────────────────────────────────────────────────────────

@app.command()
def history(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of past applications to show"),
):
    """📋 List past job applications logged in Notion."""
    apps = list_past_applications(limit)
    if not apps:
        console.print("[yellow]No past applications found in Notion.[/]")
        return

    console.print(f"\n[bold]Last {len(apps)} applications:[/]\n")
    for a in apps:
        console.print(f"  [cyan]{a['date']}[/]  {a['title']}  [{a['status']}]")
        if a.get("url"):
            console.print(f"           [dim]{a['url']}[/]")


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
