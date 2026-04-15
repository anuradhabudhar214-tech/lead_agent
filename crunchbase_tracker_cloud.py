import os
import time
import json
import logging
import requests
from datetime import datetime, timezone

# --- CONFIGURATION & LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Core Credentials (from Env or Config)
SUPABASE_URL = os.getenv("SUPABASE_URL") or "https://zsrlgjufmaecmcbqoidd.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or "sb_publishable__8ePqXcMLZ9zNaASQBuM_g_e2GUKK3e"

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

def compile_auditor_intel_deep(discovery_news, probing_results):
    """Dependency-free Gemini 2.0 call with multi-source validation."""
    key = vault.get_gemini_key()
    if not key: return "SKIP"
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
    
    prompt = f"""
    AUDIT MISSION: Final Fact Verification for UAE Intelligence.
    SOURCE A (Discovery News): {discovery_news}
    SOURCE B (Deep Probing Results): {probing_results}
    
    STRICT REQUIREMENTS:
    1. EXTRACT REAL DATA ONLY. If financial data (funding, revenue) is not EXPLICITLY stated in Source A or B, use "Searching...". No estimates.
    2. company: Exact legal or trade name.
    3. financials: Specific amounts only (e.g. 'USD $50M'). No patterns or guesses.
    4. ceo_founder: FORMAT AS 'Name (Role) - UNMASKED'. ONLY use names confirmed in the sources.
    5. registry_status: Use 'VERIFIED WITH WAM.AE' or 'VERIFIED WITH DED' only if Source B confirms a listing. Otherwise use 'UNVERIFIED'.
    6. confidence_score: 0-100 logic.
    
    RETURN JSON ONLY:
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
    Low quality or no confirmed company? score: 0.
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
        logger.error(f"❌ Gemini Deep Error: {e}")
        vault.rotate_gemini()
    return "SKIP"

def serper_search(query, timeframe="qdr:d"):
    key = vault.get_serper_key()
    if not key: return []
    url = "https://google.serper.dev/search"
    headers = {'X-API-KEY': key, 'Content-Type': 'application/json'}
    try:
        track_cloud_usage("Serper")
        payload = {"q": query, "num": 10}
        if timeframe: payload["tbs"] = timeframe
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        return r.json().get('organic', [])
    except:
        vault.rotate_serper()
    return []

def identify_company_simple(title, snippet):
    """Min-cost identification for deep probing."""
    key = vault.get_gemini_key()
    if not key: return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
    prompt = f"Extract the ONE main UAE company name mentioned in this news title/snippet. Respond with ONLY the name or 'NONE'. \nTitle: {title}\nSnippet: {snippet}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        r = requests.post(url, json=payload, timeout=10)
        name = r.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        return None if name == "NONE" else name
    except: return None

def run_tracker():
    update_agent_status("Hunting 🔴")
    niches = [
        "new tech startup UAE news April 15 2026",
        "Dubai funding announcement today",
        "Abu Dhabi Hub71 startups news today",
        "UAE tech ecosystem expansion 2026"
    ]
    niche = niches[int(time.time() / 600) % len(niches)] 
    logger.info(f"🚀 PHASE 1: DISCOVERY - '{niche}'...")
    
    news_results = serper_search(niche)
    
    for item in news_results:
        link = item.get('link')
        if not link: continue
        
        # --- Stage 2: Identification ---
        company_name = identify_company_simple(item.get('title'), item.get('snippet'))
        if not company_name: continue
        
        logger.info(f"🔍 PHASE 2: DEEP PROBE - '{company_name}'...")
        
        # --- Stage 3: Deep Verification Search ---
        probe_query = f'"{company_name}" UAE License DED site:ded.ae OR site:wam.ae OR site:linkedin.com financials funding 2026'
        probing_results = serper_search(probe_query, timeframe=None) # Comprehensive search
        
        probe_context = " | ".join([f"T: {p.get('title')} S: {p.get('snippet')}" for p in probing_results[:5]])
        news_context = f"Title: {item.get('title')} Snippet: {item.get('snippet')}"
        
        # --- Stage 4: High-Fidelity Extraction ---
        intel = compile_auditor_intel_deep(news_context, probe_context)
        
        if isinstance(intel, dict) and intel.get("company"):
            intel['url'] = link
            intel['published_date'] = item.get('date', 'April 15, 2026')
            intel['discovered_at'] = datetime.now(timezone.utc).isoformat()
            
            # --- Anti-Hallucination Polish ---
            if "USD" not in str(intel.get("financials", "")):
                intel["financials"] = "Searching..."
            
            supabase_call("POST", "uae_leads", data=intel)
            logger.info(f"✅ DEEP SYNC: {intel['company']} (Fact-Verified).")

if __name__ == "__main__":
    try:
        run_tracker()
    finally:
        update_agent_status("Sleeping 💤")
