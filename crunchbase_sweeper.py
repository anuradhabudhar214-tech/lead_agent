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

    def extract_funding_from_text(self, company, context):
        """Regex-based extraction - no AI quota needed. Reads Crunchbase text directly."""
        amount = "Undisclosed"
        round_name = "Unknown Round"
        
        # Match dollar/AED amounts: $5M, $2.5 million, AED 10M, USD 100M etc.
        amt_patterns = [
            r'\$([\d\.]+)\s*(billion|million|B|M|bn|mn)',
            r'([\d\.]+)\s*(billion|million)\s*(?:USD|AED|dollars?)',
            r'AED\s*([\d\.]+)\s*(billion|million|B|M|bn|mn)',
            r'USD\s*([\d\.]+)\s*(billion|million|B|M|bn|mn)',
            r'raised\s+\$?([\d\.]+)\s*(billion|million|B|M)',
            r'secured\s+\$?([\d\.]+)\s*(billion|million|B|M)',
            r'funding\s+of\s+\$?([\d\.]+)\s*(billion|million|B|M)',
        ]
        
        for pattern in amt_patterns:
            match = re.search(pattern, context, re.IGNORECASE)
            if match:
                num = match.group(1)
                unit = match.group(2).upper()
                if unit in ['MILLION', 'M', 'MN']: unit = 'M'
                elif unit in ['BILLION', 'B', 'BN']: unit = 'B'
                amount = f"${num}{unit}"
                break
        
        # Match funding round keywords
        round_patterns = [
            (r'pre[\-\s]?seed', 'Pre-Seed'),
            (r'seed\s+round|seed\s+funding|seed\s+stage|raised.*seed', 'Seed'),
            (r'series\s+a\b', 'Series A'),
            (r'series\s+b\b', 'Series B'),
            (r'series\s+c\b', 'Series C'),
            (r'series\s+d\b', 'Series D'),
            (r'series\s+e\b', 'Series E'),
            (r'funding\s+round|equity\s+round|financing\s+round', 'Funding Round'),
            (r'private\s+equity|equity\s+funding', 'Private Equity'),
            (r'venture\s+round|venture\s+capital\s+round', 'Venture'),
            (r'corporate\s+round|strategic\s+investment', 'Corporate'),
            (r'scale[\-\s]?up', 'Scaleup Funding'),
            (r'ipo|initial\s+public\s+offering', 'IPO'),
            (r'debt\s+financing|loan|credit\s+facility', 'Debt'),
            (r'angel\s+round|angel\s+investment', 'Angel'),
            (r'grant|award|prize', 'Grant'),
        ]
        
        for pattern, label in round_patterns:
            if re.search(pattern, context, re.IGNORECASE):
                round_name = label
                break
        
        # Build summary from first 200 chars of context
        summary = context[:200].strip() if context else f"No public funding data found for {company}"
        
        print(f"  Regex extracted: {amount} | {round_name}")
        return {"amount": amount, "round": round_name, "financials_summary": summary}

    def search_crunchbase(self, company):
        """Search Crunchbase via Google Serper for funding data."""
        if not self.serper_key:
            return ""

        queries = [
            f'site:crunchbase.com "{company}" funding raised million',
            f'"{company}" UAE startup funding round stage raised crunchbase',
            f'"{company}" "Series A" OR "Seed" OR "round" site:crunchbase.com',
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
                print(f"  Found context ({len(snippets)} chars), parsing text...")
                data = self.extract_funding_from_text(company, snippets)
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
