import os
import requests
import json

GH_PAT = os.environ.get("GH_PAT", "")
REPO = "anuradhabudhar214-tech/lead_agent"
headers = {"Accept": "application/vnd.github+json"}
if GH_PAT:
    headers["Authorization"] = f"Bearer {GH_PAT}"

# 1. Get latest run
run_req = requests.get(f"https://api.github.com/repos/{REPO}/actions/runs?per_page=1", headers=headers)
if run_req.status_code == 200:
    run = run_req.json().get('workflow_runs', [])[0]
    run_id = run['id']
    print(f"Latest Run: {run_id} | Status: {run['status']} | Conclusion: {run['conclusion']}")
    
    # 2. Get jobs for this run
    job_req = requests.get(f"https://api.github.com/repos/{REPO}/actions/runs/{run_id}/jobs", headers=headers)
    if job_req.status_code == 200:
        jobs = job_req.json().get('jobs', [])
        if jobs:
            job_id = jobs[0]['id']
            # 3. Get logs
            log_req = requests.get(f"https://api.github.com/repos/{REPO}/actions/jobs/{job_id}/logs", headers=headers)
            if log_req.status_code == 200:
                lines = log_req.text.split('\n')
                print("--- SWEEPER & ENRICHMENT LOGS ---")
                for line in lines[-200:]:
                    if "Swept" in line or "sweeper" in line.lower() or "crunchbase" in line.lower() or "error" in line.lower():
                        try: print(line.strip()[:200])
                        except: pass
            else:
                print("Could not fetch logs text.")
        else:
            print("No jobs found.")
    else:
        print("Could not fetch jobs.")
else:
    print(f"Could not fetch runs. {run_req.status_code}")
