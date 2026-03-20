"""
scripts/setup_notion_databases.py
One-time setup script to create the required Notion databases.
Run this once after setting your NOTION_API_KEY in .env

Usage:
  python scripts/setup_notion_databases.py --parent-page-id YOUR_PAGE_ID
"""

import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import typer
from notion_client import Client
from rich.console import Console
from rich import print as rprint

console = Console()
app = typer.Typer()


def create_jobs_database(client: Client, parent_page_id: str) -> str:
    """Create the Jobs tracking database."""
    response = client.databases.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        title=[{"type": "text", "text": {"content": "🎯 Job Applications"}}],
        properties={
            "Name": {"title": {}},
            "Status": {
                "select": {
                    "options": [
                        {"name": "Tailored", "color": "blue"},
                        {"name": "Applied", "color": "green"},
                        {"name": "Interview", "color": "yellow"},
                        {"name": "Offer", "color": "purple"},
                        {"name": "Rejected", "color": "red"},
                        {"name": "Withdrawn", "color": "gray"},
                    ]
                }
            },
            "Company": {"rich_text": {}},
            "Date": {"date": {}},
        },
    )
    return response["id"]


def create_outputs_database(client: Client, parent_page_id: str) -> str:
    """Create the Outputs database."""
    response = client.databases.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        title=[{"type": "text", "text": {"content": "📄 Resume & Cover Letter Outputs"}}],
        properties={
            "Name": {"title": {}},
            "Company": {"rich_text": {}},
            "Date": {"date": {}},
        },
    )
    return response["id"]


@app.command()
def setup(
    parent_page_id: str = typer.Argument(
        ..., help="Notion page ID where databases will be created"
    )
):
    """Create Notion databases for Resume Tailor."""
    api_key = os.environ.get("NOTION_API_KEY")
    if not api_key:
        console.print("[red]❌ NOTION_API_KEY not set in .env[/]")
        raise typer.Exit(1)

    client = Client(auth=api_key)

    console.print("Creating Notion databases...")

    jobs_id = create_jobs_database(client, parent_page_id)
    console.print(f"✅ Jobs database created: [cyan]{jobs_id}[/]")

    outputs_id = create_outputs_database(client, parent_page_id)
    console.print(f"✅ Outputs database created: [cyan]{outputs_id}[/]")

    console.print("\n[bold green]Add these to your .env file:[/]")
    console.print(f"NOTION_JOBS_DB_ID={jobs_id}")
    console.print(f"NOTION_OUTPUTS_DB_ID={outputs_id}")

    # Auto-write to .env if it exists
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        content = env_path.read_text()
        for key, val in [
            ("NOTION_JOBS_DB_ID", jobs_id),
            ("NOTION_OUTPUTS_DB_ID", outputs_id),
        ]:
            if key in content:
                import re
                content = re.sub(rf"{key}=.*", f"{key}={val}", content)
            else:
                content += f"\n{key}={val}"
        env_path.write_text(content)
        console.print(f"\n✅ .env file updated automatically.")


if __name__ == "__main__":
    app()
