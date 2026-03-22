# Resume Tailor

[![Version](https://img.shields.io/badge/version-0.1.0-8b5cf6.svg)](https://github.com/rotsl/resume-tailor/releases/tag/0.1.0)
[![Try it out](https://img.shields.io/badge/Try_it_out-Live_Demo-0f172a?logo=githubpages&logoColor=white)](https://rotsl.github.io/resume-tailor)
[![Visitors](https://visitor-badge.laobi.icu/badge?page_id=rotsl.resume-tailor&title=visitors&left_text=visitors)](https://rotsl.github.io/resume-tailor)

Resume Tailor takes a job description and your existing resume, then produces:

- a tailored resume
- a matching cover letter
- PDF exports for both

It can run three ways:

- as a local web app
- from the CLI
- as a static GitHub Pages app that runs in the browser

If you enable Notion, each run is automatically logged there via **Notion MCP** — a model-context protocol that routes all Notion operations through an MCP server for secure, auditable API interactions.

**Live demo:** [rotsl.github.io/resume-tailor](https://rotsl.github.io/resume-tailor)
**Privacy policy:** [rotsl.github.io/resume-tailor/privacy.html](https://rotsl.github.io/resume-tailor/privacy.html)

## What it actually does

You give the app a job description and a resume. The model rewrites and reorders your resume so it better matches the role, then drafts a cover letter based on the same source material.

The important restriction is simple: it is only supposed to use information already present in your resume. It can change emphasis, wording, and ordering. It should not invent skills, jobs, dates, metrics, or achievements.

Those rules are enforced in the prompt on every run.

## Ways to use it

### 1. GitHub Pages

The browser version lives in [`docs/index.html`](/Users/wot25kir/resume-tailor/docs/index.html). It is a single self-contained file.

You paste your API key into the page, upload or paste your files, and get PDF downloads back in the browser. Nothing goes through your own backend.

Current browser limits:

- resume input: `PDF`, `TXT`, or pasted text
- job description input: `PDF`, `TXT`, or pasted text
- no job URL fetching
- no Notion logging

### 2. Local web app

Run:

```bash
python app.py
```

Then open `http://localhost:5000`.

This version reads keys from `.env`, can fetch job descriptions from a URL, supports richer document parsing, and can log runs to Notion when configured.

### 3. CLI

Examples:

```bash
python main.py tailor --resume my_resume.pdf --job-url https://jobs.example.com/role
python main.py tailor --resume my_resume.docx --job-file job_description.pdf
python main.py tailor
python main.py history
```

The CLI can read:

- resume files in `PDF`, `DOCX`, `TXT`, or `MD`
- job descriptions from a file, a URL, pasted text, or a Notion page

## Providers

The project currently supports Anthropic Claude and Google Gemini.

| Provider | Notes | Example models in this repo |
|---|---|---|
| Claude | Paid API | `claude-opus-4-5`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001` |
| Gemini | Free tier available | `gemini-2.5-flash`, `gemini-2.5-flash-lite`, `gemini-2.5-pro` |

Claude key: [console.anthropic.com](https://console.anthropic.com)
Gemini key: [aistudio.google.com/apikey](https://aistudio.google.com/apikey)

## Notion MCP Architecture

Resume Tailor uses **Notion MCP** (Model Context Protocol) to interact with Notion. Here's how it works:

```
Your app request
    ↓
Python calls: log_job_to_notion(...)
    ↓
Routed through: Notion MCP client (src/mcp_notion_client.py)
    ↓
Spawns: Node.js MCP server (@notionhq/notion-mcp-server)
    ↓
API call: Notion REST API with your NOTION_API_KEY
    ↓
Response returned to Python
```

**Why MCP?**
- **Secure**: API key never leaves your machine, always authenticated
- **Auditable**: Each operation is a discrete MCP tool call
- **Compatible**: Works with AI models that support MCP protocol
- **Maintainable**: Decouples Notion logic from application logic

All Notion operations (`create_page`, `query_database`, `retrieve_database`, etc.) flow through this protocol automatically — no special configuration needed beyond `.env`.

## Local setup

Requirements:

- **Python** `3.11+`
- **Node.js** `18+` (required for Notion MCP server)

When you run `pip install -r requirements.txt`, it installs:
- `anthropic` — Claude API client
- `google-generativeai` — Gemini API client
- `mcp>=1.0.0` — Anthropic's Model Context Protocol client (for Notion MCP)
- `notion-client` — Optional, kept for compatibility
- Plus dependencies for PDF parsing, Flask server, CLI, etc.

The Notion MCP server (`@notionhq/notion-mcp-server`) is launched automatically by the mcp client when needed.

Install:

```bash
git clone https://github.com/YOUR_USERNAME/resume-tailor.git
cd resume-tailor

python -m venv venv
source venv/bin/activate
# Windows: venv\Scripts\activate

pip install -r requirements.txt
```

Create your env file:

```bash
cp .env.example .env
```

Then fill in the values you need:

```env
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...

NOTION_API_KEY=secret_...
NOTION_JOBS_DB_ID=
NOTION_OUTPUTS_DB_ID=
```

You only need one provider key to run the app. The Notion values are optional unless you want logging.

## Notion setup

Resume Tailor logs job applications and tailored outputs to Notion via **Notion MCP** — a protocol that routes all Notion API calls through an MCP server.

### Step 1: Create a Notion integration

1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Click "Create new integration"
3. Name it (e.g., "Resume Tailor")
4. Copy the **Internal Integration Token** (your `NOTION_API_KEY`)

### Step 2: Share a page with your integration

1. In Notion, open the page where you want Resume Tailor to create databases
2. Click the **⋯** menu → **Connections**
3. Search for your integration name and connect it

### Step 3: Get your page ID

1. Open the shared page in Notion
2. Copy the page ID from the URL: `https://www.notion.so/[your-page-id]?v=...`
3. The ID is the 32-character string before the `?`

### Step 4: Create the databases

Run the setup script to auto-create "Job Applications" and "Resume & Cover Letter Outputs" databases:

```bash
python scripts/setup_notion_databases.py YOUR_NOTION_PAGE_ID
```

This script:
- ✅ Creates two Notion databases in your specified page
- ✅ Configures required properties (Name, Status, Company, Date, etc.)
- ✅ Writes the database IDs to `.env` automatically

**How it works:** The setup script uses Notion MCP to create the databases. Each time Resume Tailor runs, it uses MCP to:
- Log job applications to the "Job Applications" database
- Save tailored resumes and cover letters to the "Resume & Cover Letter Outputs" database
- Query past applications via the CLI `history` command

## Running locally

Web app:

```bash
python app.py
```

CLI:

```bash
python main.py tailor
python main.py history
```

## Custom instructions

The file [`instruct.md`](/Users/wot25kir/resume-tailor/instruct.md) is loaded into the prompt for local and CLI runs. If you want a different resume format, section order, or cover letter style, edit that file.

The GitHub Pages version has its own inlined instructions inside [`docs/index.html`](/Users/wot25kir/resume-tailor/docs/index.html), so browser-only deployments need that copy updated too.

## Feature comparison

| Feature | GitHub Pages | Local web app | CLI |
|---|:---:|:---:|:---:|
| Claude | Yes | Yes | Yes |
| Gemini | Yes | Yes | Yes |
| PDF input | Yes | Yes | Yes |
| DOCX input | No | Yes | Yes |
| Job URL fetch | No | Yes | Yes |
| Notion logging | No | Yes | Yes |
| Read job description from Notion | No | No | Yes |
| No local install needed | Yes | No | No |

## Architecture & MCP Integration

**Key source files:**

- `src/mcp_notion_client.py` — Python MCP client that communicates with the Node.js Notion MCP server via stdio
- `src/notion_integration.py` — High-level Notion operations (`log_job_to_notion`, `read_job_from_notion_page`, etc.) that use MCP
- `.mcp.json` — MCP server configuration (Node.js `@notionhq/notion-mcp-server`)
- `scripts/setup_notion_databases.py` — One-time database setup script that also uses MCP

**How Notion MCP works:**

1. Your code calls a function like `log_job_to_notion(...)`
2. That function calls `call_notion_mcp("API-create-a-page", {...})`
3. The MCP client spawns the Node.js server: `npx @notionhq/notion-mcp-server`
4. Server uses your `NOTION_API_KEY` to authenticate with Notion API
5. Results are returned to Python in the same format as the Notion REST API

**MCP tool names used:**
- `API-retrieve-a-database` — get database schema
- `API-query-a-database` — search/list pages
- `API-create-a-page` — create new page
- `API-create-a-database` — create new database
- `API-retrieve-block-children` — read page content

## Privacy notes

In the GitHub Pages version, your resume and API key go straight from the browser to the provider you selected.

In local mode, your data is sent to the configured provider from your machine, and keys are read from `.env`.

Provider-specific data handling depends on the account tier you use. Check the provider's current policy before sending sensitive material.

## Credit

[`instruct.md`](/Users/wot25kir/resume-tailor/instruct.md) is based on the Humanizer skill here: [github.com/blader/humanizer/blob/main/SKILL.md](https://github.com/blader/humanizer/blob/main/SKILL.md)

## License

MIT. See [`LICENSE`](/Users/wot25kir/resume-tailor/LICENSE).

<br>

<div align="center">
  <sub>
    Built for people who want a sharper application packet without letting the model invent their career.
  </sub>
  <br>
  <sub>
    Claude or Gemini in, tailored PDF out, your source material stays the source of truth.
  </sub>
  <br><br>
  <sub>
    <a href="https://rotsl.github.io/resume-tailor">Live demo</a>
    ·
    <a href="https://github.com/rotsl/resume-tailor">Source</a>
  </sub>
</div>
