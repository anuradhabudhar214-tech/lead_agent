import os
import requests

r = requests.get("https://lead-agent-sigma.vercel.app/api/updates")
data = r.json()
print("Recent leads:")
for i in data[:10]:
    print(f"  {i.get('company')}: Email={i.get('contact_email')} | LinkedIn={i.get('contact_linkedin')} | Name={i.get('contact_name')}")
