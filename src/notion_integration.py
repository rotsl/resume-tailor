"""
src/notion_integration.py
Notion MCP integration — logs job applications, resume inputs, and outputs
to Notion databases. Reads job descriptions from Notion pages.

Notion MCP Server: https://github.com/makenotion/notion-mcp-server
Setup: npx @notionhq/notion-mcp-server

DESIGN: We introspect real property names from each database before writing,
so this works regardless of what Notion named the columns at creation time.
Only the title property (always present) is used for properties — everything
else is written as structured page content (blocks), which is always safe.
"""

import os
from datetime import datetime
from typing import Optional
from .mcp_notion_client import call_notion_mcp


def _get_title_property_name(db_id: str) -> str:
    """
    Introspect the database and return the name of the title property.
    Every Notion database has exactly one title property — but it may be
    named anything ('Name', 'Title', 'Job', etc.).
    """
    try:
        db = call_notion_mcp("API-retrieve-a-database", {"database_id": db_id})
        for prop_name, prop_data in db.get("properties", {}).items():
            if prop_data.get("type") == "title":
                return prop_name
    except Exception:
        pass
    return "Name"  # safe fallback


def _make_info_block(label: str, value: str) -> dict:
    """Create a callout block with a label/value pair."""
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [
                {"type": "text", "text": {"content": f"{label}: "},
                 "annotations": {"bold": True}},
                {"type": "text", "text": {"content": value}},
            ]
        },
    }


def _text_to_blocks(text: str, heading: str) -> list:
    """Convert plain text into Notion blocks under a heading_2."""
    blocks = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": heading}}]
            },
        }
    ]
    # Notion hard limit: 2000 chars per rich_text content
    chunks = [text[i: i + 1900] for i in range(0, len(text), 1900)]
    for chunk in chunks:
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": chunk}}]
            },
        })
    return blocks


# ── Read job description from a Notion page ──────────────────────────────────

def read_job_from_notion_page(page_id: str) -> str:
    """Read the content of a Notion page as plain text."""
    blocks = call_notion_mcp("API-retrieve-block-children", {"block_id": page_id})

    text_parts = []
    for block in blocks.get("results", []):
        btype = block.get("type", "")
        block_data = block.get(btype, {})
        rich_text = block_data.get("rich_text", [])
        for rt in rich_text:
            text_parts.append(rt.get("plain_text", ""))

    return "\n".join(text_parts).strip()


# ── Log a job application run to the Jobs database ───────────────────────────

def log_job_to_notion(
    job_title: str,
    company: str,
    job_description_snippet: str,
    status: str = "Tailored",
) -> Optional[str]:
    """
    Create a new entry in the Notion Jobs database.
    Only writes to the title property (always safe).
    All other info goes into the page body as blocks.
    Returns the created page ID.
    """
    db_id = os.environ.get("NOTION_JOBS_DB_ID")
    if not db_id:
        print("⚠️  NOTION_JOBS_DB_ID not set — skipping Notion job log.")
        return None

    title_prop = _get_title_property_name(db_id)
    date_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    try:
        response = call_notion_mcp(
            "API-create-a-page",
            {
                "parent": {"database_id": db_id},
                "properties": {
                    title_prop: {
                        "title": [{"text": {"content": f"{job_title} @ {company}"}}]
                    },
                },
                "children": [
                    _make_info_block("Status", status),
                    _make_info_block("Company", company),
                    _make_info_block("Date", date_str),
                    _make_info_block("Role", job_title),
                    {"object": "block", "type": "divider", "divider": {}},
                    {
                        "object": "block",
                        "type": "heading_3",
                        "heading_3": {
                            "rich_text": [{"type": "text",
                                           "text": {"content": "Job Description Snippet"}}]
                        },
                    },
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text",
                                           "text": {"content": job_description_snippet[:2000]}}]
                        },
                    },
                ],
            },
        )
        return response["id"]
    except Exception as e:
        print(f"⚠️  Notion job log failed: {e}")
        return None


# ── Save output (resume + cover letter) to Notion Outputs database ────────────

def save_outputs_to_notion(
    job_title: str,
    company: str,
    tailored_resume: str,
    cover_letter: str,
    job_page_id: Optional[str] = None,
) -> Optional[str]:
    """
    Save the tailored resume and cover letter to the Notion Outputs database.
    Only writes to the title property — all content goes in page body blocks.
    Returns the created page ID.
    """
    db_id = os.environ.get("NOTION_OUTPUTS_DB_ID")
    if not db_id:
        print("⚠️  NOTION_OUTPUTS_DB_ID not set — skipping Notion output save.")
        return None

    title_prop = _get_title_property_name(db_id)
    date_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    page_title = f"{job_title} @ {company} — {datetime.utcnow().strftime('%Y-%m-%d')}"

    try:
        children = (
            [
                _make_info_block("Company", company),
                _make_info_block("Role", job_title),
                _make_info_block("Generated", date_str),
                {"object": "block", "type": "divider", "divider": {}},
            ]
            + _text_to_blocks(tailored_resume, "📄 Tailored Resume")
            + [{"object": "block", "type": "divider", "divider": {}}]
            + _text_to_blocks(cover_letter, "✉️ Cover Letter")
        )

        response = call_notion_mcp(
            "API-create-a-page",
            {
                "parent": {"database_id": db_id},
                "properties": {
                    title_prop: {
                        "title": [{"text": {"content": page_title}}]
                    },
                },
                "children": children,
            },
        )
        return response["id"]
    except Exception as e:
        print(f"⚠️  Notion output save failed: {e}")
        return None


# ── Retrieve past applications from Notion ───────────────────────────────────

def list_past_applications(limit: int = 10) -> list:
    """List recent job applications from the Notion Jobs database."""
    db_id = os.environ.get("NOTION_JOBS_DB_ID")
    if not db_id:
        return []

    try:
        response = call_notion_mcp(
            "API-query-a-database",
            {
                "database_id": db_id,
                "sorts": [{"timestamp": "created_time", "direction": "descending"}],
                "page_size": limit,
            },
        )
        results = []
        for page in response.get("results", []):
            props = page.get("properties", {})
            # Find whichever property is the title type
            title = "Untitled"
            for prop_data in props.values():
                if prop_data.get("type") == "title":
                    parts = prop_data.get("title", [])
                    if parts:
                        title = parts[0].get("plain_text", "Untitled")
                    break
            results.append({
                "id": page["id"],
                "title": title,
                "created": page.get("created_time", "")[:10],
                "url": page.get("url", ""),
            })
        return results
    except Exception as e:
        print(f"⚠️  Could not fetch Notion applications: {e}")
        return []
