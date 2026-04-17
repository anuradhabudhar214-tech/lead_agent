import os
import requests

GH_PAT = os.environ.get("GH_PAT", "")
REPO = "anuradhabudhar214-tech/lead_agent"
headers = {"Accept": "application/vnd.github+json"}
if GH_PAT:
    headers["Authorization"] = f"Bearer {GH_PAT}"

run_id = 24508492061 # Run 91
job_req = requests.get(f"https://api.github.com/repos/{REPO}/actions/runs/{run_id}/jobs", headers=headers)
jobs = job_req.json().get("jobs", [])
job_id = jobs[0]['id']

log_req = requests.get(f"https://api.github.com/repos/{REPO}/actions/jobs/{job_id}/logs", headers=headers)
if log_req.status_code == 200:
    lines = log_req.text.split('\n')
    print("----- ENRICHMENT LOGS -----")
    for line in lines[-200:]: 
        if "apollo_enrichment.py" in line or "Enrichment" in line or "python" in line or "logger" in line or "leads" in line.lower() or "not found" in line.lower() or "error" in line.lower():
            try:
                print(line.strip()[:200])
            except Exception:
                pass
