import os, requests

GH_PAT = os.environ.get("GH_PAT", "")
REPO = "anuradhabudhar214-tech/lead_agent"
headers = {"Accept": "application/vnd.github+json"}
if GH_PAT:
    headers["Authorization"] = f"Bearer {GH_PAT}"

# Get latest run
r = requests.get(f"https://api.github.com/repos/{REPO}/actions/workflows/auditor_hunt.yml/runs?per_page=1", headers=headers)
run = r.json()["workflow_runs"][0]
run_id = run["id"]
print(f"Latest run ID: {run_id} | Status: {run['status']} | Event: {run['event']}")

# Get jobs for this run
rj = requests.get(f"https://api.github.com/repos/{REPO}/actions/runs/{run_id}/jobs", headers=headers)
jobs = rj.json().get("jobs", [])
for job in jobs:
    print(f"\nJob: {job['name']} | Status: {job['status']} | Conclusion: {job.get('conclusion')}")
    for step in job.get("steps", []):
        status_icon = "OK" if step.get("conclusion") == "success" else ("FAIL" if step.get("conclusion") == "failure" else "...")
        print(f"  [{status_icon}] Step: {step['name']} | {step.get('conclusion', step.get('status'))}")
