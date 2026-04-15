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
from google import genai

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

def track_cloud_usage(api_name):
    """Increments the usage counters in Supabase for the dashboard."""
def track_cloud_usage(call_type):
    """Updates the statistics and live status in the cloud DB."""
    if not supabase: return
    try:
        if call_type == "Serper":
            supabase.rpc("increment_serper", {"row_id": 1}).execute()
        elif call_type == "Gemini":
            supabase.rpc("increment_gemini", {"row_id": 1}).execute()
        elif call_type == "Groq":
            supabase.rpc("increment_groq", {"row_id": 1}).execute()
    except Exception as e:
        logger.debug(f"Usage tracking failed: {e}")

def update_agent_status(status):
    """Updates the live engine status (Hunting/Sleeping) and scan count."""
    if not supabase: return
    try:
        # Increment total scans if starting a new hunt
        if "Hunting" in status:
            supabase.rpc("increment_total_scans", {"row_id": 1}).execute()
            
        data = {"id": 1, "status": status, "last_run_at": "now()"}
        supabase.table("system_stats").upsert(data, on_conflict="id").execute()
        logger.info(f"📡 AGENT STATUS: {status}")
    except Exception as e:
        logger.debug(f"Status update failed: {e}")

def compile_auditor_intel(discovery_package):
    """Deep Auditor with Auto-Extraction. discovery_package contains title, snippet, link."""
    prompt = f"ROLE: Senior UAE Auditor. OBJ: Deep Audit this discovery: {discovery_package}. Instructions: 1. Identify the SINGLE most promising UAE startup. 2. Extract verified signals from WAM.ae, LinkedIn patterns, and 2026 Dubai registry news. 3. Return full JSON. fields: company, industry, financials, strategic_signal (2026 Focus), integration_opportunity, registry_status (Verified via WAM/LinkedIn), ceo_founder (Unmasked), patron_chairman, confidence_score (80-100 for clear leads). OUT: JSON."
    
    # Try all Gemini Keys before giving up
    for _ in range(len(vault.gemini_keys)):
        key = vault.get_gemini_key()
        if not key: break
        try:
            logger.info(f"💎 DEEP AUDIT: Analyzing discovery package with Gemini 2.0...")
            client = genai.Client(api_key=key)
            track_cloud_usage("Gemini")
            
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            
            data = json.loads(response.text)
            conf = data.get("confidence_score", 0)
            
            # Yesterday's Logic: 50%+ is a lead (Pending), 85%+ is Audited/Active
            if conf < 50: return "SKIP"
            
            # Ensure we have a company name
            if not data.get("company") or data.get("company").lower().startswith("top "): return "SKIP"
            
            data["status"] = "Active" if conf >= 85 else "Pending"
            return data
        except Exception as e:
            if "429" in str(e) or "limit" in str(e).lower():
                logger.warning(f"⚠️ Key Rate Limit. Rotating...")
                vault.rotate_gemini()
                continue
            logger.error(f"❌ Gemini Error: {e}")
            break

    # FALLBACK: GROQ (Optimized for 'Clear' results)
    groq_key = os.getenv("GROQ_API_KEY") or vault.config.get("GROQ_API_KEY")
    if groq_key:
        try:
            logger.info(f"⚡ FALLBACK: Groq Pro Brain for '{company_name if 'company_name' in locals() else 'package'}'")
            track_cloud_usage("Groq")
            client_groq = Groq(api_key=groq_key)
            chat_completion = client_groq.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                response_format={"type": "json_object"}
            )
            data = json.loads(chat_completion.choices[0].message.content)
            conf = data.get("confidence_score", 0)
            if conf < 50: return "SKIP"
            data["status"] = "Active" if conf >= 85 else "Pending"
            return data
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
            track_cloud_usage("Serper")
            # Added tbs: qdr:w to ensure results from the last 7 days only
            payload = {"q": query, "num": 10, "tbs": "qdr:w"}
            response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
            res_data = response.json()
            organic = res_data.get('organic', [])
            
            # Enrich organic results with their publish dates if available
            for item in organic:
                item['published_date'] = item.get('date', 'Recently')
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
                "published_date": lead.get("published_date", "Recently")
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
    # Target specific Crunchbase profiles for "Clear" results
    target_query = f"site:crunchbase.com organization UAE {niche} 2026"
    logger.info(f"🚀 24/7 HUNT: Targeting 'Clear' {niche} profiles...")
    
    raw_results = serper_search(target_query)
    for item in raw_results:
        link = item.get('link')
        if not link or link in seen_urls: continue
        
        # Pass the full discovery context to the AI for extraction
        discovery_package = f"Title: {item.get('title')} | Snippet: {item.get('snippet')} | Link: {link} | Published: {item.get('published_date')}"
        logger.info(f"🔍 AUDITING DISCOVERY: {item.get('title')[:50]}...")
        intel = compile_auditor_intel(discovery_package)
        
        if isinstance(intel, dict):
            intel['url'] = link
            intel['published_date'] = item.get('published_date')
            company = intel.get('company')
            logger.info(f"💎 FOUND CLEAR LEAD: {company} | Score: {intel.get('confidence_score')}%")
            save_to_supabase([intel])
        elif intel == "SKIP":
            logger.info(f"⏭️ SKIPPING: Discovery (Low Signal Strength)")
            
if __name__ == "__main__":
    update_agent_status("Hunting 🔴")
    try:
        run_tracker()
    finally:
        update_agent_status("Sleeping 💤")
