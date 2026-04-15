"""
scorer.py — Production Match Score Engine (Final, Micro-fixed)
"""

import re
from src.helper import ask_groq


# ══════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════
MIN_SCORE            = 30
CORE_SKILL_WEIGHT    = 2.0
UTILITY_SKILL_WEIGHT = 1.0

CORE_SKILLS = {
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust", "kotlin", "swift",
    "sql", "mysql", "postgresql", "mongodb", "redis", "cassandra", "oracle",
    "react", "angular", "vue", "node", "django", "flask", "spring", "fastapi", "express",
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform",
    "ml", "dl", "nlp", "tensorflow", "pytorch", "scikit",
    "spark", "hadoop", "kafka", "airflow", "data engineering",
    "rest", "graphql", "microservices", "system design",
}

# FIX 2 — TECH_PATTERN: "google cloud" removed (alias handles it → gcp)
# FIX 1 — "javascript" before "java" so JS is matched first, never swallowed
TECH_PATTERN = re.compile(
    r'\b('
    r'python|javascript|typescript|java|golang|ruby|php|swift|kotlin|scala|rust|perl|c\+\+|c#|'
    r'sql|mysql|postgresql|postgres|mongodb|redis|cassandra|oracle|dynamodb|sqlite|firebase|'
    r'react|angular|vue|nextjs|nuxt|svelte|'
    r'nodejs|expressjs|django|flask|fastapi|spring|laravel|rails|'
    r'aws|azure|gcp|docker|kubernetes|k8s|terraform|ansible|jenkins|'
    r'git|github|linux|bash|shell|'
    r'machine\s*learning|deep\s*learning|nlp|computer\s*vision|'
    r'tensorflow|pytorch|scikit|scikit-learn|keras|pandas|numpy|matplotlib|'
    r'spark|hadoop|kafka|airflow|dbt|snowflake|bigquery|redshift|'
    r'rest|graphql|microservices|system\s*design|'
    r'agile|scrum|jira|excel|power\s*bi|tableau|'
    r'html|css|sass|webpack|selenium|pytest|junit|postman'
    r')\b',
    re.IGNORECASE
)

ALIAS_MAP = {
    # FIX 1 — "nodejs" → "node" (matches CORE_SKILLS)
    "nodejs":           "node",
    "node.js":          "node",
    "expressjs":        "express",
    "express.js":       "express",
    "react.js":         "react",
    "reactjs":          "react",
    "vue.js":           "vue",
    "vuejs":            "vue",
    "next.js":          "nextjs",
    "postgres":         "postgresql",
    "pg":               "postgresql",
    "js":               "javascript",
    "ts":               "typescript",
    "spring boot":      "spring",
    "scikit-learn":     "scikit",
    "sklearn":          "scikit",
    "k8s":              "kubernetes",
    # FIX 2 — all forms of google cloud → single canonical "gcp"
    "google cloud":     "gcp",
    "google_cloud":     "gcp",
    "gcloud":           "gcp",
    # FIX 2 — "machine learning" / "deep learning" → "ml"/"dl" → matches CORE_SKILLS
    "machine learning": "ml",
    "deep learning":    "dl",
    "rest api":         "rest",
    "restful":          "rest",
    "ci/cd":            "cicd",
    "ci-cd":            "cicd",
    "github":           "git",
}


# ══════════════════════════════════════════════════════════════
#  NORMALIZE
# ══════════════════════════════════════════════════════════════
def normalize_skills(raw: list[str]) -> list[str]:
    seen, result = set(), []
    for s in raw:
        s = s.strip().lower()
        s = ALIAS_MAP.get(s, s)
        if s and len(s) > 1 and s not in seen:
            seen.add(s)
            result.append(s)
    result.sort(key=len, reverse=True)
    return result


# ══════════════════════════════════════════════════════════════
#  RESUME SKILL EXTRACTION
# ══════════════════════════════════════════════════════════════
def extract_resume_skills_from_summary(resume_text: str) -> list[str]:
    found        = TECH_PATTERN.findall(resume_text)
    regex_skills = normalize_skills(found)
    print(f"[Scorer] Regex found {len(regex_skills)} resume skills")

    if len(regex_skills) >= 5:
        print("[Scorer] Skipping LLM — regex sufficient")
        return regex_skills

    print("[Scorer] Calling LLM for resume skills (regex < 5)")
    prompt = f"""Extract all technical skills, tools, programming languages, and frameworks
from this resume. Return ONLY a comma-separated list. No explanation, no numbering.

Resume:
{resume_text[:2000]}"""

    raw = ask_groq(prompt, max_tokens=300)
    llm_skills = []
    if raw and "Error" not in raw:
        llm_skills = [s.strip() for s in raw.split(",") if s.strip()]
        print(f"[Scorer] LLM added {len(llm_skills)} skills")

    return normalize_skills(regex_skills + llm_skills)


# ══════════════════════════════════════════════════════════════
#  JOB SKILL EXTRACTION — regex first, LLM only if < 3, cached
# ══════════════════════════════════════════════════════════════
def extract_job_skills(job: dict) -> list[str]:
    if "_job_skills" in job:
        return job["_job_skills"]

    description = (job.get("description") or "")
    title       = (job.get("title") or "")
    full_text   = f"{title} {description}"

    if not full_text.strip():
        job["_job_skills"] = []
        return []

    found  = TECH_PATTERN.findall(full_text)
    skills = normalize_skills(found)
    print(f"[Scorer] '{title[:40]}' → regex: {len(skills)} skills")

    if len(skills) < 3 and len(description) > 100:
        print(f"[Scorer] LLM fallback for: {title[:40]}")
        prompt = f"""Extract technical skills from this job description.
Return ONLY comma-separated skills. No explanation, no numbering.

Job: {title}
Description: {description[:1000]}"""
        raw = ask_groq(prompt, max_tokens=150)
        if raw and "Error" not in raw:
            llm_skills = [s.strip() for s in raw.split(",") if s.strip()]
            skills = normalize_skills(skills + llm_skills)
            print(f"[Scorer] After LLM: {len(skills)} skills")

    job["_job_skills"] = skills[:25]
    return job["_job_skills"]


# ══════════════════════════════════════════════════════════════
#  SAFE PARTIAL MATCH
# ══════════════════════════════════════════════════════════════
def _safe_partial_match(a: str, b: str) -> bool:
    if len(a) < 4 or len(b) < 4:
        return False
    return bool(
        re.search(r'\b' + re.escape(a) + r'\b', b) or
        re.search(r'\b' + re.escape(b) + r'\b', a)
    )


# ══════════════════════════════════════════════════════════════
#  BALANCED WEIGHTED SCORING
# ══════════════════════════════════════════════════════════════
def compute_match_score(resume_skills: list[str], job_skills: list[str]) -> dict:
    if not resume_skills or not job_skills:
        return {
            "score": 0, "matched": [], "missing": [],
            "total_job_skills": len(job_skills),
            "job_coverage": 0.0, "resume_coverage": 0.0,
        }

    resume_set = set(resume_skills)   # already normalized — skip re-normalization
    job_set    = set(job_skills)

    exact_matched = resume_set & job_set
    exact_missing = job_set - resume_set

    partial_matched = set()
    for rs in (resume_set - job_set):
        for js in exact_missing:
            if _safe_partial_match(rs, js):
                partial_matched.add(js)
                break

    all_covered = exact_matched | partial_matched
    all_missing = job_set - all_covered

    def w(skill_set):
        return sum(
            CORE_SKILL_WEIGHT if s in CORE_SKILLS else UTILITY_SKILL_WEIGHT
            for s in skill_set
        )

    job_w     = w(job_set)    or 1
    resume_w  = w(resume_set) or 1
    covered_w = w(all_covered)
    hit_w     = w(resume_set & job_set)

    jc    = covered_w / job_w
    rc    = hit_w     / resume_w
    score = min(100, int((0.6 * jc + 0.4 * rc) * 100))

    sorted_missing = sorted(all_missing, key=lambda s: (0 if s in CORE_SKILLS else 1, s))

    print(f"[Scorer] Score={score} | job_cov={round(jc*100,1)}% | resume_cov={round(rc*100,1)}%")

    return {
        "score":            score,
        "matched":          sorted(all_covered),
        "missing":          sorted_missing[:5],
        "total_job_skills": len(job_set),
        "job_coverage":     round(jc * 100, 1),
        "resume_coverage":  round(rc * 100, 1),
    }


# ══════════════════════════════════════════════════════════════
#  SCORE LABEL
# ══════════════════════════════════════════════════════════════
def score_label(score: int) -> tuple[str, str]:
    if score >= 75: return "🟢 Strong Match",  "#22c55e"
    if score >= 50: return "🟡 Good Match",    "#eab308"
    if score >= 25: return "🟠 Partial Match", "#f97316"
    return              "🔴 Low Match",        "#ef4444"


# ══════════════════════════════════════════════════════════════
#  EXPLANATION
# ══════════════════════════════════════════════════════════════
def build_explanation(match: dict, job: dict) -> str:
    score   = match["score"]
    matched = match["matched"]
    missing = match["missing"]
    jc      = match["job_coverage"]
    title   = job.get("title", "this role")

    if score >= 75:
        msg = f"Strong match for **{title}**. You cover {jc}% of required skills."
    elif score >= 50:
        msg = f"Good match for **{title}**. You meet most core requirements ({jc}% job fit)."
    elif score >= 25:
        msg = f"Partial match for **{title}**. Some relevant skills present but gaps exist."
    else:
        msg = f"Low match for **{title}**. Most required skills are missing from your resume."

    if matched:
        msg += f" You already have: *{', '.join(list(matched)[:4])}*."
    if missing:
        msg += f" To improve fit, learn: *{', '.join(missing[:3])}*."

    return msg


# ══════════════════════════════════════════════════════════════
#  FILTER GARBAGE JOBS
# ══════════════════════════════════════════════════════════════
def filter_jobs(jobs: list[dict]) -> list[dict]:
    seen, clean = set(), []
    for job in jobs:
        desc = (job.get("description") or "").strip()
        if len(desc) < 50:
            continue
        key = (
            str(job.get("title", "")).lower().strip() +
            str(job.get("companyName", "") or job.get("company", "")).lower().strip()
        )
        if key in seen:
            continue
        seen.add(key)
        clean.append(job)
    print(f"[Scorer] Filter: {len(jobs)} → {len(clean)} jobs")
    return clean


# ══════════════════════════════════════════════════════════════
#  MAIN — Score + rank
# ══════════════════════════════════════════════════════════════
def score_and_rank_jobs(jobs: list[dict], resume_skills: list[str]) -> list[dict]:
    if not resume_skills:
        print("[Scorer] WARNING: resume_skills empty — returning unscored")
        return jobs

    jobs = filter_jobs(jobs)

    # Sort by description richness before capping
    jobs = sorted(jobs, key=lambda j: len(j.get("description", "")), reverse=True)
    if len(jobs) > 20:
        print(f"[Scorer] Capping {len(jobs)} → 20")
        jobs = jobs[:20]

    scored = []
    for job in jobs:
        # FIX 3 — try/except around scoring so one bad job never crashes the loop
        try:
            job_skills   = extract_job_skills(job)
            match        = compute_match_score(resume_skills, job_skills)
            label, color = score_label(match["score"])
            explanation  = build_explanation(match, job)
        except Exception as e:
            print(f"[Scorer] ERROR on job '{job.get('title','')}': {e}")
            match = {
                "score": 0, "matched": [], "missing": [],
                "job_coverage": 0.0, "resume_coverage": 0.0,
            }
            label, color = score_label(0)
            explanation  = "Could not score this job."

        job.update({
            "_score":           match["score"],
            "_matched":         match["matched"],
            "_missing":         match["missing"],
            "_label":           label,
            "_color":           color,
            "_explanation":     explanation,
            "_job_coverage":    match.get("job_coverage", 0.0),
            "_resume_coverage": match.get("resume_coverage", 0.0),
        })
        scored.append(job)

    scored.sort(key=lambda x: x["_score"], reverse=True)

    before = len(scored)
    scored = [j for j in scored if j["_score"] >= MIN_SCORE]
    print(f"[Scorer] Threshold (>={MIN_SCORE}): {before} → {len(scored)} jobs")

    return scored