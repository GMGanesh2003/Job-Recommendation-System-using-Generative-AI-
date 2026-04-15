from src.job_api import fetch_linkedin_jobs, fetch_naukri_jobs

print("=" * 40)
print("🔍 Testing Naukri...")
naukri = fetch_naukri_jobs("Python Developer")
if naukri:
    print(f"✅ Naukri working! Got {len(naukri)} jobs")
    print("Sample job:", naukri[0].get("title"), "|", naukri[0].get("companyName"))
else:
    print("❌ Naukri returned 0 jobs")

print("=" * 40)
print("🔍 Testing LinkedIn...")
linkedin = fetch_linkedin_jobs("Python Developer")
if linkedin:
    print(f"✅ LinkedIn working! Got {len(linkedin)} jobs")
    print("Sample job:", linkedin[0].get("title"), "|", linkedin[0].get("companyName"))
else:
    print("❌ LinkedIn returned 0 jobs")

print("=" * 40)
print("✅ Test Done!")