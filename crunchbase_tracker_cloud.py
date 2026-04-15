import os
import json
import time
import logging
import requests
import smtplib
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from groq import Groq
from supabase import create_client, Client
import google.generativeai as genai

# Force UTF-8 output
try:
    if sys.stdout.encoding.lower() != 'utf-8':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
except Exception:
    pass

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- SMART CREDENTIAL VAULT ---
class CredentialVault:
    def __init__(self):
        self.config = self.load_config()
        self.serper_keys = self.config.get("SERPER_API_KEYS", [])
        self.gemini_keys = self.config.get("GEMINI_API_KEYS", [])
        self.serper_idx = 0
        self.gemini_idx = 0

    def load_config(self):
        # Load from Env first (Cloud), then local config
        config = {}
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                config = json.load(f)
        
        # Override with Env Vars if present
        env_serper = os.getenv("SERPER_API_KEYS")
        if env_serper: config["SERPER_API_KEYS"] = env_serper.split(",")
        
        env_gemini = os.getenv("GEMINI_API_KEYS")
        if env_gemini: config["GEMINI_API_KEYS"] = env_gemini.split(",")
        
        return config

    def get_serper_key(self):
        if not self.serper_keys: return None
        return self.serper_keys[self.serper_idx % len(self.serper_keys)].strip()

    def rotate_serper(self):
        self.serper_idx += 1
        logger.warning(f"🔄 SERPER ROTATION: Switching to Key #{self.serper_idx % len(self.serper_keys) + 1}")

    def get_gemini_key(self):
        if not self.gemini_keys: return None
        return self.gemini_keys[self.gemini_idx % len(self.gemini_keys)].strip()

    def rotate_gemini(self):
        self.gemini_idx += 1
        logger.warning(f"🔄 GEMINI ROTATION: Switching to Identity #{self.gemini_idx % len(self.gemini_keys) + 1}")

vault = CredentialVault()

# Initialize Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL") or vault.config.get("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or vault.config.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None

def compile_auditor_intel(company_name):
    """Infinite Audit Engine with Auto-Rotation."""
    prompt = f"ROLE: Senior UAE Auditor. OBJ: Verify '{company_name}'. Rules: Zero-Trust Founders, GCC Only, No Rupees, Score 1-100. Min 70. OUT: JSON object."
    
    # Try all Gemini Keys before giving up
    for _ in range(len(vault.gemini_keys)):
        key = vault.get_gemini_key()
        if not key: break
        try:
            logger.info(f"💎 AUDIT: Analyzing '{company_name}' with Gemini...")
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
            data = json.loads(response.text)
            if data.get("confidence_score", 0) < 70: return "SKIP"
            return data
        except Exception as e:
            if "429" in str(e) or "limit" in str(e).lower():
                vault.rotate_gemini()
                continue
            logger.error(f"❌ Gemini Error: {e}")
            break

    # FALLBACK: GROQ (If all Gemini fail)
    groq_key = os.getenv("GROQ_API_KEY") or vault.config.get("GROQ_API_KEY")
    if groq_key:
        try:
            logger.info(f"⚡ FALLBACK: Groq Llama 3.3 Audit for '{company_name}'")
            client = Groq(api_key=groq_key)
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                response_format={"type": "json_object"}
            )
            return json.loads(chat_completion.choices[0].message.content)
        except Exception as e:
            logger.error(f"❌ Final Fallback Error: {e}")
    
    return "RETRY"

def serper_search(query):
    """Infinite Search with Auto-Rotation."""
    for _ in range(len(vault.serper_keys)):
        key = vault.get_serper_key()
        if not key: return []
        url = "https://google.serper.dev/search"
        headers = {'X-API-KEY': key, 'Content-Type': 'application/json'}
        try:
            response = requests.post(url, headers=headers, data=json.dumps({"q": query, "num": 10}), timeout=10)
            res_data = response.json()
            if response.status_code != 200:
                vault.rotate_serper()
                continue
            return res_data.get('organic', [])
        except:
            vault.rotate_serper()
            continue
    return []

def save_to_supabase(leads):
    if not supabase or not leads: return
    for lead in leads:
        try:
            data = {
                "company": lead.get("company"),
                "industry": lead.get("industry"),
                "confidence_score": lead.get("confidence_score"),
                "patron_chairman": lead.get("patron_chairman"),
                "ceo_founder": lead.get("ceo_founder"),
                "financials": lead.get("financials"),
                "strategic_signal": lead.get("strategic_signal"),
                "integration_opportunity": lead.get("integration_opportunity"),
                "registry_status": lead.get("registry_status"),
                "url": lead.get("url"),
                "status": lead.get("status", "Pending")
            }
            supabase.table("uae_leads").upsert(data, on_conflict="company").execute()
            logger.info(f"✅ SYNC: {lead.get('company')} to Cloud DB.")
        except Exception as e:
            logger.error(f"❌ DB Error: {e}")

def run_tracker():
    seen_urls = []
    if supabase:
        try:
            res = supabase.table("uae_leads").select("url").execute()
            seen_urls = [r['url'] for r in res.data] if res.data else []
        except: pass

    niches = vault.config.get("NICHES", ["UAE AI startups 2026"])
    niche = niches[int(time.time() / 3600) % len(niches)]
    logger.info(f"🚀 24/7 HUNT: Scanning '{niche}'")
    
    raw_results = serper_search(niche)
    for item in raw_results:
        link = item.get('link')
        if not link or link in seen_urls: continue
        company = item.get('title', '').split("-")[0].strip()
        intel = compile_auditor_intel(company)
        
        if isinstance(intel, dict):
            intel['url'] = link
            logger.info(f"💎 FOUND: {company} | Score: {intel.get('confidence_score')}%")
            save_to_supabase([intel])
        elif intel == "SKIP":
            save_to_supabase([{"company": company, "url": link, "status": "Discarded"}])
            
if __name__ == "__main__":
    run_tracker()
