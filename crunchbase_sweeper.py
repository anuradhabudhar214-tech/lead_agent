import os
import requests
import json
import time
from supabase import create_client, Client
import re

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SERPER_API_KEYS = os.environ.get("SERPER_API_KEYS", "")
GEMINI_API_KEYS = os.environ.get("GEMINI_API_KEYS", "")

class CrunchbaseSweeper:
    def __init__(self):
        self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None
        self.serper_key = SERPER_API_KEYS.split(',')[0].strip() if SERPER_API_KEYS else None
        self.gemini_key = GEMINI_API_KEYS.split(',')[0].strip() if GEMINI_API_KEYS else None

    def ask_gemini_funding(self, company, context):
        if not self.gemini_key: return "Undisclosed", "Unknown Round", context
        
        prompt = f"""
        Extract the exact funding amount and funding round for the company '{company}' based ONLY on this text from Crunchbase:
        "{context}"
        
        If not explicitly listed in the text, return "Undisclosed".
        RETURN ONLY JSON in this exact format:
        {{"amount": "$5M", "round": "Series A", "financials_summary": "Raised $5M in Series A led by XYZ Mgt."}}
        """
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_key}", json=payload)
            text = r.json()['candidates'][0]['content']['parts'][0]['text']
            text = re.sub(r"```json|```", "", text).strip()
            return json.loads(text)
        except:
            return {"amount": "Undisclosed", "round": "Unknown Round", "financials_summary": context}

    def sweep(self):
        if not self.supabase: return
        res = self.supabase.table("uae_leads").select("id, company").is_("funding_amount", "null").limit(5).execute()
        leads = res.data
        if not leads: return
        
        for lead in leads:
            company = lead['company']
            query = f'"{company}" funding OR raised site:crunchbase.com'
            try:
                r = requests.post("https://google.serper.dev/search", headers={"X-API-KEY": self.serper_key}, json={"q": query})
                snippets = " ".join([x.get('snippet', '') for x in r.json().get('organic', [])])
                if snippets:
                    data = self.ask_gemini_funding(company, snippets)
                    self.supabase.table("uae_leads").update({
                        "funding_amount": data.get("amount", "Undisclosed"),
                        "funding_round": data.get("round", "Unknown Round"),
                        "financials": data.get("financials_summary", "")
                    }).eq("id", lead['id']).execute()
                    print(f"Swept {company}: {data.get('amount')}")
                else:
                    self.supabase.table("uae_leads").update({"funding_amount": "Undisclosed", "funding_round": "Unknown Round"}).eq("id", lead['id']).execute()
            except Exception as e:
                pass

if __name__ == "__main__":
    CrunchbaseSweeper().sweep()
