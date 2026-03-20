"""
app.py  — Local Flask server (python app.py → http://localhost:5000)
For GitHub Pages deployment, see docs/index.html + .github/workflows/deploy.yml
"""

import os, sys, uuid, threading, re
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template_string, abort
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from src.parser import extract_text
from src.web_context import fetch_company_context
from src.tailor import tailor_resume, generate_cover_letter
from src.pdf_generator import generate_resume_pdf, generate_cover_letter_pdf
from src.notion_integration import log_job_to_notion, save_outputs_to_notion

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
OUTPUT_DIR = Path("outputs"); OUTPUT_DIR.mkdir(exist_ok=True)
jobs: dict = {}

ENV_ANTHROPIC = os.environ.get("ANTHROPIC_API_KEY", "")
ENV_GEMINI    = os.environ.get("GEMINI_API_KEY", "")

# ── HTML ──────────────────────────────────────────────────────────────────────
with open(Path(__file__).parent / "docs" / "index.html", encoding="utf-8") as f:
    _TEMPLATE = f.read()

@app.route("/")
def index():
    html = _TEMPLATE \
        .replace("__ANTHROPIC_KEY__", ENV_ANTHROPIC or "") \
        .replace("__GEMINI_KEY__",    ENV_GEMINI    or "") \
        .replace("__GITHUB_PAGES__",  "false")
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}

# ── API ───────────────────────────────────────────────────────────────────────
@app.route("/api/tailor", methods=["POST"])
def start_tailor():
    provider = request.form.get("provider", "claude").strip()
    model    = request.form.get("model", "").strip()
    api_key  = request.form.get("api_key", "").strip() or \
               (ENV_ANTHROPIC if provider == "claude" else ENV_GEMINI)
    if not api_key:
        return jsonify({"error": f"No API key for {provider}."}), 400

    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "running", "step": 0}

    job_url = request.form.get("job_url","").strip()
    job_text = request.form.get("job_text","").strip()
    resume_text = request.form.get("resume_text","").strip()
    job_fb, job_fn = (b := request.files.get("job_file")) and (b.read(), b.filename) or (None,"")
    res_fb, res_fn = (b := request.files.get("resume_file")) and (b.read(), b.filename) or (None,"")

    threading.Thread(target=_run, args=(
        job_id, provider, model, api_key,
        job_url, job_text, job_fb, job_fn,
        resume_text, res_fb, res_fn
    ), daemon=True).start()
    return jsonify({"job_id": job_id})


def _run(job_id, provider, model, api_key,
         job_url, job_text, job_fb, job_fn,
         resume_text, res_fb, res_fn):
    def step(n): jobs[job_id]["step"] = n
    try:
        step(0)
        if job_fb:
            jd = extract_text(job_fb, job_fn)
        elif job_url:
            import httpx
            try:
                r = httpx.get(job_url, timeout=15, follow_redirects=True,
                              headers={"User-Agent":"Mozilla/5.0"})
                jd = re.sub(r"\s+"," ", re.sub(r"<[^>]+>"," ", r.text)).strip()[:8000]
            except Exception: jd = job_text or ""
        else: jd = job_text
        resume = extract_text(res_fb, res_fn) if res_fb else resume_text
        if not jd.strip() or not resume.strip():
            jobs[job_id]={"status":"error","error":"Could not extract text."}; return

        step(1); web_ctx = fetch_company_context(jd, job_url or "")
        step(2); tailored = tailor_resume(resume, jd, web_ctx, provider=provider, model=model, api_key=api_key)
        step(3); cover    = generate_cover_letter(resume, jd, tailored, web_ctx, provider=provider, model=model, api_key=api_key)

        step(4)
        cm = re.search(r"(?:at|@|for|join)\s+([A-Z][A-Za-z0-9&\s]{2,30}?)(?:\s*[,.]|\s+is\b|\s+we\b)", jd)
        company = cm.group(1).strip() if cm else "Company"
        lines = [l.strip() for l in jd.split("\n") if l.strip()]
        job_title = lines[0][:50] if lines else "Role"
        rp = str(OUTPUT_DIR/f"{job_id}_resume.pdf")
        cp = str(OUTPUT_DIR/f"{job_id}_cover.pdf")
        generate_resume_pdf(tailored, rp)
        generate_cover_letter_pdf(cover, cp)

        step(5); notion_saved = False
        if os.environ.get("NOTION_API_KEY") and os.environ.get("NOTION_JOBS_DB_ID"):
            try:
                nid = log_job_to_notion(job_title, company, jd[:500])
                save_outputs_to_notion(job_title, company, tailored, cover, nid)
                notion_saved = True
            except Exception: pass

        jobs[job_id]={"status":"done","step":6,"resume_path":rp,"cover_path":cp,
                      "company":company,"job_title":job_title,"notion_saved":notion_saved}
    except Exception as e:
        jobs[job_id]={"status":"error","error":str(e)}


@app.route("/api/status/<job_id>")
def job_status(job_id):
    j = jobs.get(job_id)
    if not j: abort(404)
    return jsonify({**j, "job_id": job_id})

@app.route("/api/download/<job_id>/<doc>")
def download(job_id, doc):
    j = jobs.get(job_id)
    if not j or j.get("status") != "done": abort(404)
    path = j["resume_path"] if doc == "resume" else j["cover_path"]
    name = f"{'Resume' if doc=='resume' else 'CoverLetter'}_{j.get('company','')}.pdf"
    return send_file(path, as_attachment=True, download_name=name, mimetype="application/pdf")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n🎯 Resume Tailor → http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
