import os
import requests
import zipfile
import io

GH_PAT = os.environ.get("GH_PAT", "")
REPO = "anuradhabudhar214-tech/lead_agent"
headers = {"Accept": "application/vnd.github+json"}
if GH_PAT:
    headers["Authorization"] = f"Bearer {GH_PAT}"

# Get the last 5 runs to safely capture any failures
r = requests.get(f"https://api.github.com/repos/{REPO}/actions/workflows/auditor_hunt.yml/runs?per_page=5", headers=headers)
runs = r.json().get("workflow_runs", [])

found_failure = False
for run in runs:
    print(f"Run {run['run_number']} - Status: {run['status']} - Conclusion: {run.get('conclusion')}")
    if run.get('conclusion') == 'failure' or run.get('status') == 'failed':
        found_failure = True
        run_id = run['id']
        print(f"Fetching complete failure logs for Run {run['run_number']}...")
        
        # Get logs from jobs
        job_req = requests.get(f"https://api.github.com/repos/{REPO}/actions/runs/{run_id}/jobs", headers=headers)
        jobs = job_req.json().get("jobs", [])
        for job in jobs:
            if job.get('conclusion') == 'failure':
                job_id = job['id']
                log_req = requests.get(f"https://api.github.com/repos/{REPO}/actions/jobs/{job_id}/logs", headers=headers)
                if log_req.status_code == 200:
                    lines = log_req.text.split('\n')
                    print("\n--- ERROR LOG EXTRACT ---")
                    # Find lines with traceback
                    for i, line in enumerate(lines):
                        if 'Traceback' in line or 'Error' in line or 'Exception' in line:
                            # Print the error block safely encoding for terminal
                            start = max(0, i - 1)
                            end = min(len(lines), i + 20)
                            for l in lines[start:end]:
                                try:
                                    print(l.strip())
                                except UnicodeEncodeError:
                                    print("[UNICODE LINE OMITTED]")
                            break
                    print("-" * 25)
        break # Only check the most recent failure

if not found_failure:
    print("NO FAILURES FOUND in the last 5 runs! All runs succeeded.")
