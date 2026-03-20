# Resume Tailor

[![Version](https://img.shields.io/badge/version-v0.0.1-8b5cf6.svg)](https://github.com/rotsl/resume-tailor/releases/tag/v0.0.1)
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

If you enable Notion, each run can also be logged there through MCP.

**Live demo:** [rotsl.github.io/resume-tailor](https://rotsl.github.io/resume-tailor)

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

## Local setup

Requirements:

- Python `3.11+`
- Node.js `18+` if you want the Notion MCP flow

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

If you want job history and saved outputs in Notion:

1. Create a Notion integration at [notion.so/my-integrations](https://www.notion.so/my-integrations).
2. Share the target page with that integration.
3. Copy the page ID from the URL.
4. Run:

```bash
python scripts/setup_notion_databases.py YOUR_NOTION_PAGE_ID
```

The script creates the two databases the app expects and writes their IDs into `.env`.

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
