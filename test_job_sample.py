from src.job_api import fetch_linkedin_jobs, fetch_naukri_jobs

linkedin_jobs = fetch_linkedin_jobs("Python Developer", "India", 2)
naukri_jobs   = fetch_naukri_jobs("Python Developer", "India", 2)

if linkedin_jobs:
    print("=== LINKEDIN SAMPLE ===")
    print(linkedin_jobs[0])

if naukri_jobs:
    print("=== NAUKRI SAMPLE ===")
    print(naukri_jobs[0])