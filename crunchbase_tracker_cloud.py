import os
import time
import json
import logging
import requests
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client
from groq import Groq
import google.generativeai as genai

# --- CONFIGURATION & LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None

class Vault:
    def __init__(self):
        # Load from config.json if available locally, otherwise env
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
        logger.info(f"🔄 Rotated Serper Key to index {self.serper_idx % len(self.serper_keys)}")

    def get_gemini_key(self):
        return self.gemini_keys[self.gemini_idx % len(self.gemini_keys)] if self.gemini_keys else None

    def rotate_gemini(self):
        self.gemini_idx += 1
        logger.info(f"🔄 Rotated Gemini Key to index {self.gemini_idx % len(self.gemini_keys)}")

vault = Vault()

def track_cloud_usage(api_name):
    """Increments token usage in Supabase 'system_stats' table."""
    if not supabase: return
    try:
        col = f"{api_name.lower()}_calls"
        res = supabase.table("system_stats").select(col).eq("id", 1).execute()
        if res.data:
            new_val = (res.data[0].get(col) or 0) + 1
            supabase.table("system_stats").update({col: new_val, "last_updated": datetime.now(timezone.utc).isoformat()}).eq("id", 1).execute()
    except Exception as e:
        logger.error(f"⚠️ Usage Tracking Error: {e}")

def update_agent_status(status):
    """Updates the live status heartbeat on the dashboard."""
    if not supabase: return
    try:
        data = {
            "status": status,
            "last_run_at": datetime.now(timezone.utc).isoformat()
        }
        if status == "Hunting 🔴":
            res = supabase.table("system_stats").select("total_scans").eq("id", 1).execute()
            if res.data and "total_scans" in res.data[0]:
                data["total_scans"] = (res.data[0]["total_scans"] or 0) + 1
        
        supabase.table("system_stats").update(data).eq("id", 1).execute()
    except Exception as e:
        logger.error(f"⚠️ Status Sync Error: {e}")

def compile_auditor_intel(discovery_package):
    """Uses Gemini 2.0 Flash to extract executive intelligence."""
    prompt = f"""
    AUDIT MISSION: Extract UAE Tech Intelligence from this discovery.
    CONTEXT: {discovery_package}
    
    REQUIREMENTS:
    1. Identify the Company Name.
    2. Extract Industry (e.g. AI, FinTech, GreenTech).
    3. Assign Confidence Score (0-100) based on how clearly this is a real UAE 2026/2027 business signal.
    4. Strategic Signal: News summary.
    5. Integration Opportunity: For an auditor.
    6. Executive Unmasking: Find CEO/Founder.
    7. Financials: Funding or revenue.
    8. Registry Status: Verified if official.
    
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
    Low info? score: 0.
    """
    
    for _ in range(len(vault.gemini_keys)):
        key = vault.get_gemini_key()
        if not key: break
        try:
            track_cloud_usage("Gemini")
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-2.0-flash')
            response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
            
            data = json.loads(response.text)
            conf = data.get("confidence_score", 0)
            if conf < 50: return "SKIP"
            if not data.get("company") or data.get("company").lower().startswith("top "): return "SKIP"
            
            data["status"] = "Active" if conf >= 85 else "Pending"
            return data
        except Exception as e:
            if "429" in str(e):
                vault.rotate_gemini()
                continue
            logger.error(f"❌ Gemini Error: {e}")
            break
    return "SKIP"

def serper_search(query):
    """Infinite Search with Auto-Rotation and 24h Freshness."""
    for _ in range(len(vault.serper_keys)):
        key = vault.get_serper_key()
        if not key: return []
        url = "https://google.serper.dev/search"
        headers = {'X-API-KEY': key, 'Content-Type': 'application/json'}
        try:
            track_cloud_usage("Serper")
            # qdr:d = Past 24 hours to ensure freshness
            payload = {"q": query, "num": 10, "tbs": "qdr:d"}
            response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
            res_data = response.json()
            organic = res_data.get('organic', [])
            for item in organic:
                item['published_date'] = item.get('date', 'Live Signal')
            return organic
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
                "status": lead.get("status", "Pending"),
                "published_date": lead.get("published_date", "Recently"),
                "discovered_at": datetime.now(timezone.utc).isoformat()
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

    # --- AGGRESSIVE NICHES ---
    niches = [
        "Dubai tech startups funding news April 2026",
        "Abu Dhabi Hub71 startups news April 2026",
        "UAE new VC funding April 2026",
        "Dubai Silicon Oasis startup hiring 2026",
        "UAE Ministry of Economy tech grants 2026",
        "Abu Dhabi crypto funding news 2026",
        "Dubai Internet City expansion startups 2026",
        "UAE SpaceTech startup funding 2026"
    ]
    
    niche = niches[int(time.time() / 600) % len(niches)] 
    target_query = f"site:crunchbase.com organization UAE {niche}"
    logger.info(f"🚀 DEEP HUNT: '{niche}'...")
    
    raw_results = serper_search(target_query)
    for item in raw_results:
        link = item.get('link')
        if not link or link in seen_urls: continue
        
        discovery_package = f"Title: {item.get('title')} | Snippet: {item.get('snippet')} | Link: {link} | Published: {item.get('published_date')}"
        logger.info(f"🔍 AUDITING: {item.get('title')[:30]}...")
        intel = compile_auditor_intel(discovery_package)
        
        if isinstance(intel, dict):
            intel['url'] = link
            intel['published_date'] = item.get('published_date')
            save_to_supabase([intel])
            
if __name__ == "__main__":
    update_agent_status("Hunting 🔴")
    try:
        run_tracker()
    finally:
        update_agent_status("Sleeping 💤")
