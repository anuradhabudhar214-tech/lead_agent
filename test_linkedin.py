import os
import requests
import json
import re

SERPER_KEY = os.environ.get("SERPER_API_KEYS", "").split(',')[0].strip()

# Gemini found these names:
targets = [
    {"name": "Saad Mansoor", "company": "Nym Card"},
    {"name": "Tariq Bin Hendi", "company": "Bayanat"},
]

for target in targets:
    name = target["name"]
    company = target["company"]
    print(f"\n--- Testing: {name} at {company} ---")
    query = f'"{name}" "{company}" site:linkedin.com/in/'
    print(f"Google Query: {query}")
    
    try:
        r = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"},
            json={"q": query, "num": 5},
            timeout=10
        )
        results = r.json().get("organic", [])
        for i, res in enumerate(results[:3]):
            print(f"  ACTUAL LINK EXTRACTED: {res.get('link')}")
    except Exception as e:
        print(f"Error: {e}")
