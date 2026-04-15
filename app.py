import io
import json
import streamlit as st
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm

from src.helper  import extract_text_from_pdf, ask_groq
from src.job_api import fetch_linkedin_jobs, fetch_naukri_jobs, get_job_link
from src.scorer  import score_and_rank_jobs, extract_resume_skills_from_summary

st.set_page_config(page_title="AI Job Recommender", layout="wide", page_icon="📄")

# ══════════════════════════════════════════════════════════════
#  CSS  — single unified block
# ══════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── Base ── */
body, .stApp {
    background-color: #ffffff;
    color: #1f2937 !important;
}
.stMarkdown, p, li {
    color: #374151 !important;
}
.block-container { padding-top: 2rem; }
.section-gap     { margin-top: 2.5rem; margin-bottom: 0.5rem; }
hr               { margin: 0.6rem 0 !important; }

/* ── Card ── */
.card {
    background: #f3f4f6;
    padding: 1rem 1.2rem;
    border-radius: 12px;
    border: 1px solid #d1d5db;
    margin-bottom: 1rem;
    color: #000000 !important;
}
.card h3, .card p, .card span, .card div {
    color: #000000 !important;
}

/* ── Dashboard metric cards ── */
.dash-card {
    background: linear-gradient(135deg, #f3f4f6, #ffffff);
    border: 1px solid #d1d5db;
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    text-align: center;
    color: #000000 !important;
}
.dash-card .metric-val {
    font-size: 2.2rem;
    font-weight: 800;
    color: #0ea5e9;
    line-height: 1.1;
}
.dash-card .metric-label {
    font-size: 0.8rem;
    color: #000000;
    margin-top: 0.3rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
}

/* ── Top job banner ── */
.top-job-banner {
    background: linear-gradient(90deg, #f0fdf4, #dcfce7);
    border-left: 4px solid #22c55e;
    border-radius: 8px;
    padding: 0.8rem 1.2rem;
    margin-bottom: 0.5rem;
    color: #000000 !important;
}

/* ── Confidence badges ── */
.badge-high   { background:#dcfce7; color:#000000; padding:3px 10px; border-radius:99px; font-size:0.75rem; font-weight:700; }
.badge-medium { background:#fef3c7; color:#000000; padding:3px 10px; border-radius:99px; font-size:0.75rem; font-weight:700; }
.badge-low    { background:#fee2e2; color:#000000; padding:3px 10px; border-radius:99px; font-size:0.75rem; font-weight:700; }

/* ── Skill tags ── */
.tag-matched {
    background: #22c55e;
    color: #ffffff;
    padding: 4px 8px;
    border-radius: 6px;
    margin: 2px;
    display: inline-block;
    font-size: 0.78rem;
    font-weight: 600;
}
.tag-missing {
    background: #f97316;
    color: #ffffff;
    padding: 4px 8px;
    border-radius: 6px;
    margin: 2px;
    display: inline-block;
    font-size: 0.78rem;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

# ── Title ──────────────────────────────────────────────────────
st.markdown("<h1 style='color:#38bdf8;'>📄 AI Job Recommender</h1>", unsafe_allow_html=True)
st.markdown("Upload your resume and get smart, **ranked** job recommendations 🚀")
st.markdown("---")

uploaded_file = st.file_uploader("Upload your resume (PDF)", type=["pdf"])

DEFAULT_KEYWORDS = ["Software Developer", "Backend Developer", "Data Analyst"]


# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════
def fallback_search_link(role: str, platform: str) -> str:
    r = urllib.parse.quote(role)
    if platform == "LinkedIn":
        return f"https://www.linkedin.com/jobs/search/?keywords={r}&location=India"
    elif platform == "Naukri":
        return f"https://www.naukri.com/{urllib.parse.quote(role.lower().replace(' ', '-'))}-jobs"
    return f"https://www.google.com/search?q={urllib.parse.quote(role + ' jobs India')}&ibp=htl;jobs"


def fetch_with_timeout(fn, *args, timeout=90):
    with ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(fn, *args)
        try:
            return future.result(timeout=timeout)
        except FutureTimeout:
            print(f"[App] TIMEOUT: {fn.__name__}")
            return []
        except Exception as e:
            print(f"[App] ERROR {fn.__name__}: {e}")
            return []


def confidence_badge(score: int) -> str:
    if score >= 75:
        return "<span class='badge-high'>🟢 High Confidence</span>"
    elif score >= 50:
        return "<span class='badge-medium'>🟡 Medium Confidence</span>"
    return "<span class='badge-low'>🔴 Low Confidence</span>"


def render_tags(skills: list, tag_class: str):
    """Render colour-coded skill pill tags."""
    if not skills:
        return
    tags = " ".join(f"<span class='{tag_class}'>{s}</span>" for s in skills)
    st.markdown(tags, unsafe_allow_html=True)


def render_score(score: int, jc: int, rc: int, color: str):
    """Centred score block + progress bar + formula caption."""
    st.markdown(
        f"""<div style="text-align:center;">
            <div style="font-size:24px;font-weight:800;color:{color};">{score}/100</div>
            <div style="font-size:13px;color:#94a3b8;">Job fit: {jc}% | Resume hit: {rc}%</div>
        </div>""",
        unsafe_allow_html=True,
    )
    st.progress(score / 100)
    st.caption("Score = 60% job match + 40% resume strength")


def render_section_card(title: str, content: str):
    """Render a dark card with a title and markdown content."""
    st.markdown(
        f"<div class='card'><h3 style='color:#38bdf8;margin-top:0'>{title}</h3>"
        f"<div style='color:#e2e8f0'>{content}</div></div>",
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════
#  PDF REPORT GENERATOR
# ══════════════════════════════════════════════════════════════
def generate_pdf(data: list) -> bytes:
    buffer = io.BytesIO()
    doc    = SimpleDocTemplate(buffer, rightMargin=2*cm, leftMargin=2*cm,
                               topMargin=2*cm, bottomMargin=2*cm)
    styles   = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("AI Job Recommender — Match Report", styles["Title"]))
    elements.append(Spacer(1, 0.4*cm))

    for i, job in enumerate(data[:10], 1):
        title    = job.get("title", "N/A")
        company  = job.get("company", "N/A")
        score    = job.get("score", 0)
        matched  = ", ".join(job.get("matched", [])) or "—"
        missing  = ", ".join(job.get("missing", [])) or "—"
        platform = job.get("platform", "")

        elements.append(Paragraph(
            f"<b>{i}. {title}</b> @ {company} [{platform}] — {score}/100",
            styles["Heading3"]
        ))
        elements.append(Paragraph(f"Matched Skills: {matched}", styles["Normal"]))
        elements.append(Paragraph(f"Missing Skills: {missing}",  styles["Normal"]))
        elements.append(Spacer(1, 0.3*cm))

    doc.build(elements)
    return buffer.getvalue()


# ══════════════════════════════════════════════════════════════
#  GROQ ANALYSIS
# ══════════════════════════════════════════════════════════════
def analyze_resume_once(resume_text: str) -> dict:
    result = {"summary": "", "gaps": "", "roadmap": "", "roles_raw": ""}

    prompt = f"""Analyze this resume and return exactly 4 sections with these headers:

### SUMMARY
(Write a clear 4-5 line professional summary including skills, education, experience level, and strengths)

### SKILL_GAPS
(Provide detailed and actionable gaps:
- Missing technical skills
- Missing tools/technologies
- Industry expectations vs current profile
- Certifications or projects needed
- Explain WHY each gap matters in 1 line)

### ROADMAP
(Create a step-by-step improvement plan:
1. Short-term (1-2 months)
2. Mid-term (3-6 months)
3. Long-term (6+ months)
Include skills, projects, and learning path)

### JOB_ROLES
(comma-separated list of top 3 suitable job roles only, no explanation)

Resume:
{resume_text[:3000]}
"""

    raw = ask_groq(prompt, max_tokens=1200)

    if not raw or "Error" in raw:
        print("[App] WARNING: Merged Groq call failed")
        return result

    sections = {
        "summary":   "### SUMMARY",
        "gaps":      "### SKILL_GAPS",
        "roadmap":   "### ROADMAP",
        "roles_raw": "### JOB_ROLES",
    }

    for key, header in sections.items():
        if header in raw:
            result[key] = raw.split(header)[1].split("###")[0].strip()

    print(f"[App] Analysis done — filled: {[k for k, v in result.items() if v]}")
    return result

# ══════════════════════════════════════════════════════════════
#  DASHBOARD
# ══════════════════════════════════════════════════════════════
def render_dashboard(resume_skills: list, ranked_linkedin: list, ranked_naukri: list):
    st.markdown("<div class='section-gap'></div>", unsafe_allow_html=True)
    st.markdown("## 📊 Your Profile Overview")

    all_jobs  = ranked_linkedin + ranked_naukri
    avg_score = (
        sum(j["_score"] for j in all_jobs[:10]) // max(1, min(10, len(all_jobs)))
        if all_jobs else 0
    )
    top_score = max((j["_score"] for j in all_jobs), default=0)

    c1, c2, c3, c4 = st.columns(4)
    for col, val, label in [
        (c1, len(resume_skills),                        "Skills Detected"),
        (c2, len(ranked_linkedin) + len(ranked_naukri), "Jobs Found"),
        (c3, f"{avg_score}%",                           "Avg Match Score"),
        (c4, f"{top_score}%",                           "Best Match"),
    ]:
        with col:
            st.markdown(
                f"<div class='dash-card'>"
                f"<div class='metric-val'>{val}</div>"
                f"<div class='metric-label'>{label}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )


# ══════════════════════════════════════════════════════════════
#  JOB CARD  — clean version
# ══════════════════════════════════════════════════════════════
def render_job_card(job: dict, platform: str, fallback_role: str, rank: int = 99):
    title    = job.get("title") or job.get("positionName") or job.get("jobTitle") or "No Title"
    company  = job.get("companyName") or job.get("company") or job.get("employer") or "Unknown"
    location = job.get("location") or job.get("jobLocation") or "Not specified"
    salary   = job.get("salary") or job.get("salaryRange") or job.get("ctc") or ""
    link     = get_job_link(job)

    score       = job.get("_score", 0)
    matched     = job.get("_matched", [])
    missing     = job.get("_missing", [])
    label       = job.get("_label", "")
    explanation = job.get("_explanation", "")
    jc          = job.get("_job_coverage", 0)
    rc          = job.get("_resume_coverage", 0)

    # Score colour
    if score >= 75:
        color = "#22c55e"
    elif score >= 50:
        color = "#eab308"
    else:
        color = "#ef4444"

    # Rank banners
    if rank == 0:
        st.markdown(
            "<div class='top-job-banner'>"
            "🥇 <strong>Top Match</strong> — Best fit for your resume 🔥"
            "</div>",
            unsafe_allow_html=True,
        )
    elif rank == 1:
        st.info("🥈 2nd Best Match")
    elif rank == 2:
        st.info("🥉 3rd Best Match")

    st.markdown("<div class='card'>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([4, 2, 1])

    with col1:
        st.subheader(title)
        meta = f"🏢 {company}   📍 {location}"
        if salary:
            meta += f"   💰 {salary}"
        st.caption(meta)
        st.markdown(confidence_badge(score), unsafe_allow_html=True)

    with col2:
        render_score(score, jc, rc, color)

    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        if link:
            st.link_button("Apply →", link, use_container_width=True)
        else:
            st.link_button("Search →", fallback_search_link(fallback_role, platform),
                           use_container_width=True)

    if explanation:
        st.markdown(f"> {explanation}")

    st.markdown("---")

    sc1, sc2 = st.columns(2)
    with sc1:
        if matched:
            st.markdown("**✅ Matched Skills**")
            render_tags(matched[:6], "tag-matched")
            st.caption(f"{len(matched)} skills matched")
    with sc2:
        if missing:
            st.markdown("**⚠️ Missing Skills**")
            render_tags(missing, "tag-missing")
            st.info(f"📚 Recommended to learn: {', '.join(missing[:3])}")

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("---")


# ══════════════════════════════════════════════════════════════
#  RESULTS SECTION
# ══════════════════════════════════════════════════════════════
def render_results_section(
    ranked: list,
    platform: str,
    header: str,
    keyword_list: list,
    min_score: int = 30,
    search_term: str = "",
):
    st.markdown("<div class='section-gap'></div>", unsafe_allow_html=True)
    st.header(header)
    st.markdown("---")

    filtered = [j for j in ranked if j["_score"] >= min_score]
    if search_term:
        filtered = [
            j for j in filtered
            if search_term.lower() in (j.get("title") or j.get("positionName") or "").lower()
        ]

    if not filtered:
        st.warning(
            f"⚠️ No {platform} jobs match your filters (score ≥ {min_score}"
            + (f", search: '{search_term}'" if search_term else "") + ")."
        )
        st.link_button("🔍 Search manually", fallback_search_link(keyword_list[0], platform))
        return

    top = filtered[0]
    st.markdown(
        f"<div class='top-job-banner'>"
        f"🏆 Best: <strong>{top.get('title','N/A')}</strong> @ "
        f"<strong>{top.get('companyName','N/A')}</strong> — "
        f"{top['_label']} &nbsp;<strong>({top['_score']}/100)</strong>"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.caption(f"{len(filtered)} quality jobs found · Sorted by match score (descending)")

    if filtered[0]["_score"] < 50:
        st.warning("⚠️ No strong matches found — showing closest options")

    st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)

    for i, job in enumerate(filtered):
        render_job_card(job, platform, keyword_list[0], rank=i)


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════
if uploaded_file:

    with st.spinner("🤖 AI is reading your resume..."):
        resume_text = extract_text_from_pdf(uploaded_file)[:3000]

    if not resume_text.strip():
        st.error("❌ Could not read PDF. Please try a different file.")
        st.stop()

    with st.spinner("🤖 AI is analyzing your resume..."):
        analysis = analyze_resume_once(resume_text)

    if not any(analysis.values()):
        st.warning("⚠️ Resume analysis failed. Job search will still work with reduced accuracy.")

    summary      = analysis["summary"]
    gaps         = analysis["gaps"]
    roadmap      = analysis["roadmap"]
    keywords_raw = analysis["roles_raw"]

    with st.spinner("🔍 Extracting your skills..."):
        resume_skills = extract_resume_skills_from_summary(resume_text)

    if not resume_skills:
        st.warning("⚠️ Could not extract skills from resume. Scoring may be limited.")

    # ── Analysis cards ────────────────────────────────────────
    st.markdown("<div class='section-gap'></div>", unsafe_allow_html=True)
    render_section_card("📑 Resume Summary", summary if summary else "_Summary not available._")

    if resume_skills:
        tags = " ".join(f"<span class='tag-matched'>{s}</span>" for s in resume_skills)
        st.markdown(f"**🧠 Detected Skills:** {tags}", unsafe_allow_html=True)

    st.markdown("---")
    render_section_card("🛠️ Skill Gaps", gaps if gaps else "_Skill gaps not available._")

    st.markdown("---")
    render_section_card("🚀 Career Roadmap", roadmap if roadmap else "_Roadmap not available._")

    st.markdown("---")
    st.success("✅ Analysis Complete!")

    # Parse keyword list
    keyword_list = [k.strip().strip('"\'') for k in keywords_raw.split(",") if k.strip()][:3]
    if not keyword_list:
        print("[App] WARNING: keyword_list empty — using defaults")
        keyword_list = DEFAULT_KEYWORDS
        st.warning("⚠️ Could not detect job roles — using default search terms.")

    st.markdown("<div class='section-gap'></div>", unsafe_allow_html=True)

    if st.button("🔎 Get Live Job Recommendations", use_container_width=True):

        st.success(f"🔑 Searching for: **{', '.join(keyword_list)}**")

        all_linkedin, all_naukri = [], []
        total_steps = len(keyword_list) * 2
        bar = st.progress(0, text="Initialising fetch...")

        for i, kw in enumerate(keyword_list):
            bar.progress((i * 2)     / total_steps, text=f"⏳ LinkedIn → {kw}")
            all_linkedin += fetch_with_timeout(fetch_linkedin_jobs, kw, "India", 5, timeout=90)

            bar.progress((i * 2 + 1) / total_steps, text=f"⏳ Naukri → {kw}")
            all_naukri   += fetch_with_timeout(fetch_naukri_jobs,   kw, "India", 5, timeout=90)

        bar.progress(1.0, text="✅ Fetch complete!")
        print(f"[App] Fetched → LinkedIn: {len(all_linkedin)}, Naukri: {len(all_naukri)}")

        if not all_linkedin and not all_naukri:
            st.error("❌ No jobs fetched from any platform. Check Apify credits or network.")
            st.stop()

        with st.spinner("⭐ Scoring and ranking all jobs..."):
            ranked_linkedin = score_and_rank_jobs(all_linkedin, resume_skills) if all_linkedin else []
            ranked_naukri   = score_and_rank_jobs(all_naukri,   resume_skills) if all_naukri   else []

        # Dashboard
        render_dashboard(resume_skills, ranked_linkedin, ranked_naukri)

        # Filters + Search
        st.markdown("<div class='section-gap'></div>", unsafe_allow_html=True)
        st.markdown("### 🎛️ Filter Results")
        fcol1, fcol2 = st.columns([2, 3])
        with fcol1:
            min_score = st.slider("Minimum Match Score", 0, 100, 30, step=5)
        with fcol2:
            search_term = st.text_input("🔍 Search by job title")

        # PDF Download
        all_ranked = ranked_linkedin + ranked_naukri
        if all_ranked:
            report_data = [
                {
                    "platform": "LinkedIn" if j in ranked_linkedin else "Naukri",
                    "title":    j.get("title") or j.get("positionName") or "N/A",
                    "company":  j.get("companyName") or j.get("company") or "N/A",
                    "location": j.get("location") or j.get("jobLocation") or "N/A",
                    "score":    j.get("_score", 0),
                    "label":    j.get("_label", ""),
                    "matched":  j.get("_matched", []),
                    "missing":  j.get("_missing", []),
                    "link":     get_job_link(j) or "",
                }
                for j in sorted(all_ranked, key=lambda x: x.get("_score", 0), reverse=True)
            ]
            pdf_bytes = generate_pdf(report_data)
            st.download_button(
                label="📄 Download Report (PDF)",
                data=pdf_bytes,
                file_name="job_report.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

        st.markdown("---")

        # Job Results
        render_results_section(
            ranked_linkedin, "LinkedIn", "💼 LinkedIn Jobs",
            keyword_list, min_score, search_term
        )
        render_results_section(
            ranked_naukri, "Naukri", "🟠 Naukri Jobs",
            keyword_list, min_score, search_term
        )