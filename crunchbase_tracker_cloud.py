import os
import time
import json
import logging
import requests
import csv
from datetime import datetime, timezone

# --- CONFIGURATION & LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Core Credentials (from Env or Config)
SUPABASE_URL = os.getenv("SUPABASE_URL") or "https://zsrlgjufmaecmcbqoidd.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or "sb_publishable__8ePqXcMLZ9zNaASQBuM_g_e2GUKK3e"
CSV_FILE = "enterprise_leads.csv"

class Vault:
    def __init__(self):
        self.config = {}
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                self.config = json.load(f)
        self.serper_keys = os.getenv("SERPER_API_KEYS", "").split(",") or self.config.get("SERPER_API_KEYS", [])
        self.gemini_keys = os.getenv("GEMINI_API_KEYS", "").split(",") or self.config.get("GEMINI_API_KEYS", [])
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
        "company": "string",
        "industry": "string",
        "confidence_score": int,
        "strategic_signal": "string",
        "integration_opportunity": "string",
        "patron_chairman": "string",
        "ceo_founder": "string",
        "financials": "string",
        "registry_status": "string"
    }}
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"}
    }
    
    try:
        track_cloud_usage("Gemini")
        r = requests.post(url, json=payload, timeout=15)
        res_data = r.json()
        text = res_data['candidates'][0]['content']['parts'][0]['text']
        data = json.loads(text)
        
        if data.get("confidence_score", 0) < 50: return "SKIP"
        data["status"] = "Active" if data.get("confidence_score", 0) >= 85 else "Pending"
        return data
    except Exception as e:
        logger.error(f"❌ Gemini Extreme Error: {e}")
        vault.rotate_gemini()
    return "SKIP"

def serper_search_broad(query):
    """Max-Volume Serper discovery (50 results per call)."""
    key = vault.get_serper_key()
    if not key: return []
    url = "https://google.serper.dev/search"
    headers = {'X-API-KEY': key, 'Content-Type': 'application/json'}
    try:
        track_cloud_usage("Serper")
        # num: 50 for max results per credit spent
        payload = {"q": query, "num": 50, "tbs": "qdr:d"} 
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        return r.json().get('organic', [])
    except:
        vault.rotate_serper()
    return []

def run_tracker():
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
                supabase_call("POST", "uae_leads", data=intel)
                save_to_csv(intel)
                logger.info(f"✅ HARVESTED: {intel['company']} (Cloud + Local CSV)")

if __name__ == "__main__":
    try:
        run_tracker()
    finally:
        update_agent_status("Sleeping 💤")
