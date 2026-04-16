import os
import requests
import json
import re

SERPER_KEY = os.environ.get("SERPER_API_KEYS", "").split(',')[0].strip()
company = "Pallapay"

print(f"Testing Serper strategy for: {company}")
queries = [
    f'"{company}" CEO email site:linkedin.com OR site:crunchbase.com',
    f'"{company}" founder CTO email UAE contact',
    f'"{company}" "@" CEO OR founder OR CTO UAE',
]

found_email = None
for query in queries:
    print(f"  → Searching query: {query}")
    try:
        r = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"},
            json={"q": query, "num": 5},
            timeout=10
        )
        if r.status_code != 200:
            print(f"    Serper Error: {r.status_code} ({r.text})")
            continue
            
        results = r.json().get("organic", [])
        for result in results:
            snippet = result.get("snippet", "") + " " + result.get("title", "")
            print(f"    Snippet: {snippet[:100]}")
            email_match = re.search(r'[\w.+-]+@[\w-]+\.[a-z]{2,4}', snippet)
            if email_match:
                found_email = email_match.group(0)
                print(f"    ✅ MATCH FOUND: {found_email}")
                break
        if found_email: break
    except Exception as e:
        print(f"    Error: {e}")

if not found_email:
    print("  ❌ No email found via Serper. Fallback would hit Gemini next.")
