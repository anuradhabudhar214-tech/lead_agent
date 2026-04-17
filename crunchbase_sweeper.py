import os
import requests
import json
import time
from supabase import create_client, Client
import re

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SERPER_API_KEYS = os.environ.get("SERPER_API_KEYS", os.environ.get("SERPER_API_KEY", ""))
GEMINI_API_KEYS = os.environ.get("GEMINI_API_KEYS", os.environ.get("GEMINI_API_KEY", ""))

class CrunchbaseSweeper:
    def __init__(self):
        self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None
        self.serper_key = SERPER_API_KEYS.split(',')[0].strip() if SERPER_API_KEYS else None
        self.gemini_key = GEMINI_API_KEYS.split(',')[0].strip() if GEMINI_API_KEYS else None

    def ask_gemini_funding(self, company, context):
        if not self.gemini_key:
            return {"amount": "Undisclosed", "round": "Unknown Round", "financials_summary": context}

        prompt = f"""You are a financial data extractor. Given Crunchbase search results for '{company}', extract funding info.

Search results: "{context}"

Rules:
- Look for phrases like "raised $X", "secured $X", "Series A", "Seed round", "$X million", etc.
- amount: exact dollar amount with symbol (e.g. "$5M", "$2.5M", "AED 10M"). If none found, return "Undisclosed".
- round: the funding round stage (e.g. "Seed", "Series A", "Series B", "Pre-Seed"). If none found, return "Unknown Round".

RETURN ONLY valid JSON, no markdown:
{{"amount": "$5M", "round": "Series A", "financials_summary": "Raised $5M Series A led by XYZ."}}"""

        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_key}",
                json=payload, timeout=15
            )
            text = r.json()['candidates'][0]['content']['parts'][0]['text']
            text = re.sub(r"```json|```", "", text).strip()
            data = json.loads(text)
            print(f"  Gemini extracted: {data.get('amount')} | {data.get('round')}")
            return data
        except Exception as e:
            print(f"  Gemini error: {e}")
            return {"amount": "Undisclosed", "round": "Unknown Round", "financials_summary": context[:200]}

    def search_crunchbase(self, company):
        """Search Crunchbase via Google Serper for funding data."""
        if not self.serper_key:
            return ""

        queries = [
            f'site:crunchbase.com "{company}" funding raised million',
            f'"{company}" UAE startup funding round raised crunchbase',
        ]

        all_snippets = []
        for query in queries:
            try:
                r = requests.post(
                    "https://google.serper.dev/search",
                    headers={"X-API-KEY": self.serper_key, "Content-Type": "application/json"},
                    json={"q": query, "num": 5},
                    timeout=10
                )
                results = r.json().get('organic', [])
                for res in results:
                    snippet = res.get('snippet', '')
                    title = res.get('title', '')
                    if snippet:
                        all_snippets.append(f"{title}: {snippet}")
                time.sleep(1)
            except Exception as e:
                print(f"  Serper error: {e}")

        return " | ".join(all_snippets)

    def sweep(self):
        if not self.supabase:
            print("No Supabase connection")
            return

        # BUG FIX: Fetch ALL 200 records, then filter locally to catch NULL, "Undisclosed", "None"
        all_leads = []
        for page in range(4):  # Fetch up to 200 records (4 pages x 50)
            res = self.supabase.table("uae_leads").select("id, company, funding_amount, funding_round") \
                .range(page * 50, page * 50 + 49).execute()
            if not res.data:
                break
            all_leads.extend(res.data)

        # Filter only those that still need sweeping
        leads = [
            l for l in all_leads
            if not l.get('funding_amount') or l.get('funding_amount') in ['Undisclosed', 'None', 'Unknown Round', '']
        ]

        print(f"Found {len(leads)} leads needing funding audit out of {len(all_leads)} total...")
        if not leads:
            print("All leads already have funding data!")
            return

        for lead in leads[:50]:  # Process up to 50 per run
            company = lead['company']
            print(f"\nSearching Crunchbase for: {company}")
            snippets = self.search_crunchbase(company)

            if snippets and len(snippets) > 30:
                print(f"  Found context ({len(snippets)} chars), asking Gemini...")
                data = self.ask_gemini_funding(company, snippets)
            else:
                print(f"  No Crunchbase funding data found for {company}")
                data = {
                    "amount": "Undisclosed",
                    "round": "Unknown Round",
                    "financials_summary": "Not publicly listed on Crunchbase"
                }

            try:
                self.supabase.table("uae_leads").update({
                    "funding_amount": data.get("amount", "Undisclosed"),
                    "funding_round": data.get("round", "Unknown Round"),
                    "financials": data.get("financials_summary", "")
                }).eq("id", lead['id']).execute()
                print(f"  Updated: {company} -> {data.get('amount')} | {data.get('round')}")
            except Exception as e:
                print(f"  DB error: {e}")

            time.sleep(2)


if __name__ == "__main__":
    CrunchbaseSweeper().sweep()
