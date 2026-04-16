import os, requests
headers={'Accept': 'application/vnd.github+json'}
if os.getenv('GH_PAT'):
    headers['Authorization'] = 'Bearer ' + os.getenv('GH_PAT')
r=requests.get('https://api.github.com/repos/anuradhabudhar214-tech/lead_agent/actions/workflows/auditor_hunt.yml/runs?per_page=5', headers=headers)
for x in r.json().get('workflow_runs', []):
    print(f"Event: {x['event']} | Status: {x['status']} | Started: {x['created_at']}")
