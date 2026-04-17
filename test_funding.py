import os
import requests
import json

SERPER_KEY = os.environ.get("SERPER_API_KEYS", "").split(',')[0].strip()
companies = ["Nym Card", "Bayanat"]

for company in companies:
    print(f"\n--- Testing: {company} ---")
    query = f'"{company}" funding round amount raised site:crunchbase.com'
    
    try:
        r = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"},
            json={"q": query, "num": 3},
            timeout=10
        )
        results = r.json().get("organic", [])
        for i, res in enumerate(results):
            print(f"  Snippet: {res.get('snippet')}")
    except Exception as e:
        print(f"Error: {e}")
