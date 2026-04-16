import os
import requests

GH_PAT = os.environ.get("GH_PAT", "")
REPO = "anuradhabudhar214-tech/lead_agent"
headers = {"Accept": "application/vnd.github+json"}
if GH_PAT:
    headers["Authorization"] = f"Bearer {GH_PAT}"

r = requests.get(f"https://api.github.com/repos/{REPO}/actions/workflows/auditor_hunt.yml/runs?per_page=10", headers=headers)
runs = r.json()["workflow_runs"]
for run in runs:
    print(f"Run {run['run_number']} | Created: {run['created_at']} | Status: {run['status']} | Conclusion: {run.get('conclusion')} | Event: {run['event']}")
