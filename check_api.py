import requests

r = requests.get("https://lead-agent-sigma.vercel.app/api/updates")
if r.status_code == 200:
    leads = r.json()
    for lead in leads[:10]:
        print(f"Company: {lead.get('company')}")
        print(f"  Amt: {lead.get('funding_amount')}")
        print(f"  Round: {lead.get('funding_round')}")
        print(f"  Fin: {lead.get('financials')}")
else:
    print(f"Error {r.status_code}")
