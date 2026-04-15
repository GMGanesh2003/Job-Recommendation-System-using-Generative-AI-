from apify_client import ApifyClient
import os
from dotenv import load_dotenv

load_dotenv()

apify_client = ApifyClient(os.getenv("APIFY_API_TOKEN"))


def get_job_link(job: dict) -> str:
    """Try all possible link field names Apify actors return."""
    for field in ["jobUrl", "url", "link", "applyUrl", "jobLink",
                "linkedinUrl", "externalApplyUrl", "applyLink", "jobUrlOnApify"]:
        val = job.get(field)
        if val and str(val).startswith("http"):
            return val
    return ""


# -------- LINKEDIN --------
def fetch_linkedin_jobs(search_query, location="India", rows=5):
    try:
        run_input = {
            "title": search_query,
            "location": location,
            "rows": rows,
            "proxy": {"useApifyProxy": True},
        }

        # timeout=120 seconds max — won't hang forever
        run = apify_client.actor("BHzefUZlZRKWxkTck").call(
            run_input=run_input,
            timeout_secs=120,
            memory_mbytes=256,
        )

        if not run or not run.get("defaultDatasetId"):
            print("LinkedIn: No dataset returned")
            return []

        jobs = list(apify_client.dataset(run["defaultDatasetId"]).iterate_items())
        print(f"LinkedIn fetched: {len(jobs)} jobs for '{search_query}'")
        return jobs

    except Exception as e:
        print(f"LinkedIn Error for '{search_query}': {e}")
        return []


# -------- NAUKRI --------
def fetch_naukri_jobs(search_query, location="India", rows=5):
    try:
        run_input = {
            "keyword": search_query,
            "location": location,
            "maxJobs": rows,          # FIX: was max(rows,50) — forced 50 minimum
            "freshness": "all",
            "sortBy": "relevance",
            "experience": "all",
        }

        # timeout=120 seconds max — won't hang forever
        run = apify_client.actor("qA8rz8tR61HdkfTBL").call(
            run_input=run_input,
            timeout_secs=120,
            memory_mbytes=256,
        )

        if not run or not run.get("defaultDatasetId"):
            print("Naukri: No dataset returned")
            return []

        jobs = list(apify_client.dataset(run["defaultDatasetId"]).iterate_items())
        print(f"Naukri fetched: {len(jobs)} jobs for '{search_query}'")
        return jobs

    except Exception as e:
        print(f"Naukri Error for '{search_query}': {e}")
        return []
    
