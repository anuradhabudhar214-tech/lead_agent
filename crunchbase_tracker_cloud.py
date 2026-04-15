import os
import time
import json
import logging
import requests
import csv
from datetime import datetime, timezone
from groq import Groq

# --- CONFIGURATION & LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from supabase import create_client, Client

# Core Credentials (from Env or Config)
SUPABASE_URL = os.getenv("SUPABASE_URL") or "https://zsrlgjufmaecmcbqoidd.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or "sb_publishable__8ePqXcMLZ9zNaASQBuM_g_e2GUKK3e"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None

CSV_FILE = "enterprise_leads.csv"

class Vault:
    def __init__(self):
        self.config = {}
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                self.config = json.load(f)
        serper_env = os.getenv("SERPER_API_KEYS", "")
        gemini_env = os.getenv("GEMINI_API_KEYS", "")
        self.serper_keys = [k for k in serper_env.split(",") if k] or self.config.get("SERPER_API_KEYS", [])
        self.gemini_keys = [k for k in gemini_env.split(",") if k] or self.config.get("GEMINI_API_KEYS", [])
        self.serper_idx = 0
        self.gemini_idx = 0

    def get_serper_key(self):
        return self.serper_keys[self.serper_idx % len(self.serper_keys)] if self.serper_keys else None
    
    def rotate_serper(self):
        self.serper_idx += 1
        logger.info(f"🔄 Rotated Serper Key")

    def get_gemini_key(self):
        return self.gemini_keys[self.gemini_idx % len(self.gemini_keys)] if self.gemini_keys else None

    def rotate_gemini(self):
        self.gemini_idx += 1
        logger.info(f"🔄 Rotated Gemini Key")

vault = Vault()

def supabase_call(method, table, data=None, params=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    try:
        if method == "GET":
            return requests.get(url, headers=headers, params=params).json()
        elif method == "POST":
            return requests.post(url, headers=headers, json=data)
        elif method == "PATCH":
            return requests.patch(url, headers=headers, json=data, params=params)
    except Exception as e:
        logger.error(f"❌ Supabase Error: {e}")
    return None

def track_cloud_usage(api_name):
    try:
        col = f"{api_name.lower()}_calls"
        res = supabase_call("GET", "system_stats", params={"id": "eq.1", "select": col})
        if res:
            new_val = (res[0].get(col) or 0) + 1
            supabase_call("PATCH", "system_stats", data={col: new_val, "last_updated": datetime.now(timezone.utc).isoformat()}, params={"id": "eq.1"})
    except: pass

def update_agent_status(status):
    try:
        data = {"status": status, "last_run_at": datetime.now(timezone.utc).isoformat()}
        if status == "Hunting 🔴":
            res = supabase_call("GET", "system_stats", params={"id": "eq.1", "select": "total_scans"})
            if res: data["total_scans"] = (res[0].get("total_scans") or 0) + 1
        supabase_call("PATCH", "system_stats", data=data, params={"id": "eq.1"})
    except: pass

def save_to_csv(lead):
    """Saves lead to local CSV backup matching your format."""
    file_exists = os.path.exists(CSV_FILE)
    headers = ["Confidence", "Company", "Industry", "Patron/Chairman", "CEO/Founder", "Financials", "2026 Strategic Signal", "Integration Opportunity", "Registry Status", "URL", "Discovered At"]
    try:
        with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            if not file_exists:
                writer.writeheader()
            writer.writerow({
                "Confidence": lead.get("confidence_score"),
                "Company": lead.get("company"),
                "Industry": lead.get("industry"),
                "Patron/Chairman": lead.get("patron_chairman"),
                "CEO/Founder": lead.get("ceo_founder"),
                "Financials": lead.get("financials"),
                "2026 Strategic Signal": lead.get("strategic_signal"),
                "Integration Opportunity": lead.get("integration_opportunity"),
                "Registry Status": lead.get("registry_status"),
                "URL": lead.get("url"),
                "Discovered At": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            })
    except Exception as e:
        logger.error(f"❌ CSV Backup Error: {e}")

def compile_auditor_intel_extreme(discovery_package):
    """High-Volume Gemini 2.0 extraction maximized for 3000 leads daily."""
    key = vault.get_gemini_key()
    if not key: return "SKIP"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
    
    prompt = f"""
    AUDIT MISSION: Extract as much UAE startup intelligence as possible from this source.
    CONTEXT: {discovery_package}
    
    INSTRUCTION: Extract the main company and any secondary startups mentioned.
    1. EXTRACT REAL DATA ONLY. No guesses.
    2. financials: Only state facts found. If not found, use 'Searching...'.
    3. ceo_founder: FORMAT AS 'Name (Role) - UNMASKED'.
    4. registry_status: Only say VERIFIED if the source explicitly confirms it. Otherwise say 'PROBING...'.
    5. RETURN JSON ONLY.
    
    FORMAT:
    {{
        "company": "string (or 'Ecosystem News' if no specific company)",
        "industry": "string",
        "confidence_score": int,
        "strategic_signal": "string (Main summary)",
        "integration_opportunity": "string",
        "patron_chairman": "string",
        "ceo_founder": "string",
        "financials": "string",
        "registry_status": "string"
    }}
    Low quality / No relevance? score: 0.
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"}
    }
    
    try:
        track_cloud_usage("Gemini")
        r = requests.post(url, json=payload, timeout=15)
        res_data = r.json()
        if 'error' in res_data:
            if res_data['error'].get('code') == 429:
                raise Exception("429 Quota Exceeded")
        text = res_data['candidates'][0]['content']['parts'][0]['text']
        data = json.loads(text)
        
        if data.get("confidence_score", 0) < 40: return "SKIP"
        if not data.get("company") or data.get("company") == "": data["company"] = "UAE Tech Sector"
        data["status"] = "Active" if data.get("confidence_score", 0) >= 85 else "Pending"
        return data
    except Exception as e:
        logger.error(f"⚠️ Gemini Exhausted/Error: {e}")
        vault.rotate_gemini()
        # FALLBACK: GROQ
        groq_key = os.getenv("GROQ_API_KEY") or vault.config.get("GROQ_API_KEY")
        if groq_key:
            try:
                logger.info(f"⚡ FALLBACK: Groq Activated")
                track_cloud_usage("Groq")
                client_groq = Groq(api_key=groq_key)
                chat_completion = client_groq.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="llama-3.3-70b-versatile",
                    response_format={"type": "json_object"}
                )
                data = json.loads(chat_completion.choices[0].message.content)
                conf = data.get("confidence_score", 0)
                if conf < 40: return "SKIP"
                if not data.get("company") or data.get("company") == "": data["company"] = "UAE Tech Sector"
                data["status"] = "Active" if conf >= 85 else "Pending"
                return data
            except Exception as ex:
                logger.error(f"❌ Final Fallback Error: {ex}")
    return "SKIP"

def serper_search_broad(query):
    """Max-Volume Serper discovery (50 results per call)."""
    for _ in range(len(vault.serper_keys)):
        key = vault.get_serper_key()
        if not key: return []
        url = "https://google.serper.dev/search"
        headers = {'X-API-KEY': key, 'Content-Type': 'application/json'}
        try:
            track_cloud_usage("Serper")
            # num: 50 for max results per credit spent
            payload = {"q": query, "num": 50, "tbs": "qdr:d"} 
            r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
            res_data = r.json()
            if 'organic' in res_data:
                return res_data['organic']
            # If no organic results, it might be an error or quota exceeded.
            vault.rotate_serper()
        except:
            vault.rotate_serper()
            continue
    return []

def run_tracker():
    # Check if manually paused
    if supabase:
        try:
            res = supabase.table("system_stats").select("status").eq("id", 1).execute()
            if res.data and res.data[0].get("status") == "Paused ⏸️":
                logger.info("Agent is manually paused. Skipping hunt.")
                return
        except Exception as e:
            pass

    update_agent_status("Hunting 🔴")
    niches = [
        "Dubai AI and Blockchain startups investment news 2026",
        "UAE Venture Capital funding rounds today",
        "Abu Dhabi Hub71 startups funding announcements April 2026",
        "UAE Tech ecosystem expansion recruitment 2026"
    ]
    
    # Process 2 niches per run to stay under your 3000/day target velocity
    current_niches = [niches[int(time.time() / 300) % len(niches)], 
                      niches[(int(time.time() / 300) + 1) % len(niches)]]
                      
    for niche in current_niches:
        logger.info(f"🚀 GLOBAL HARVEST: '{niche}'...")
        results = serper_search_broad(niche)
        
        for item in results:
            discovery_package = f"Title: {item.get('title')} | Snippet: {item.get('snippet')} | Date: {item.get('date')}"
            intel = compile_auditor_intel_extreme(discovery_package)
            
            if isinstance(intel, dict) and intel.get("company"):
                intel['url'] = item.get('link')
                intel['discovered_at'] = datetime.now(timezone.utc).isoformat()
                
                # --- DUAL STORAGE: Supabase + CSV ---
                if supabase:
                    try:
                        supabase.table("uae_leads").upsert(intel, on_conflict="company").execute()
                    except Exception as e:
                        logger.error(f"❌ DB Error: {e}")
                save_to_csv(intel)
                logger.info(f"✅ HARVESTED: {intel['company']} (Cloud + Local CSV)")

if __name__ == "__main__":
    try:
        run_tracker()
    finally:
        update_agent_status("Sleeping 💤")
