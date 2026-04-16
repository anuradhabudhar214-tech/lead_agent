import os
import time
import json
import logging
import requests
import csv
from datetime import datetime, timezone
from groq import Groq

# --- CONFIGURATION & LOGGING (Engine Heartbeat Poke) ---
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
        groq_env = os.getenv("GROQ_API_KEYS", "") or os.getenv("GROQ_API_KEY", "")
        self.serper_keys = [k.strip() for k in serper_env.split(",") if k.strip()] or self.config.get("SERPER_API_KEYS", [])
        self.gemini_keys = [k.strip() for k in gemini_env.split(",") if k.strip()] or self.config.get("GEMINI_API_KEYS", [])
        self.groq_keys = [k.strip() for k in groq_env.split(",") if k.strip()] or self.config.get("GROQ_API_KEY", [])
        if isinstance(self.groq_keys, str): self.groq_keys = [self.groq_keys]
        self.serper_idx = 0
        self.gemini_idx = 0
        self.groq_idx = 0
        self.dead_keys = set()

    def get_serper_key(self):
        return self.serper_keys[self.serper_idx % len(self.serper_keys)] if self.serper_keys else None
    
    def rotate_serper(self):
        self.serper_idx += 1
        logger.info(f"🔄 Rotated Serper Key")

    def get_gemini_key(self):
        for _ in range(len(self.gemini_keys)):
            key = self.gemini_keys[self.gemini_idx % len(self.gemini_keys)]
            if key not in self.dead_keys: return key
            self.gemini_idx += 1
        return None

    def mark_key_dead(self, key):
        self.dead_keys.add(key)
        logger.warning(f"💀 KEY BLACKLISTED: {key[:8]}... marked as dead/invalid.")

    def rotate_gemini(self):
        self.gemini_idx += 1
        logger.info(f"🔄 Rotated Gemini Key")

    def get_groq_key(self):
        return self.groq_keys[self.groq_idx % len(self.groq_keys)] if self.groq_keys else None

    def rotate_groq(self):
        self.groq_idx += 1
        logger.info(f"🔄 Rotated Groq Key")

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
    """Updates the cloud dashboard status with extreme reliability."""
    try:
        now = datetime.now(timezone.utc)
        data = {"status": status, "last_run_at": now.isoformat()}
        
        # Only do the 'Reset' and 'Scan Count' logic when waking up or starting a hunt
        if "Hunting" in status or "Waking" in status:
            res_stats = supabase_call("GET", "system_stats", params={"id": "eq.1", "select": "last_run_at,total_scans"})
            if isinstance(res_stats, list) and len(res_stats) > 0:
                last_run_at = res_stats[0].get("last_run_at")
                if last_run_at:
                    try:
                        last_dt = datetime.fromisoformat(last_run_at.replace("Z", "+00:00"))
                        if last_dt.date() < now.date():
                            data.update({"gemini_calls": 0, "groq_calls": 0, "total_scans": 0})
                        if last_dt.month < now.month or last_dt.year < now.year:
                            data.update({"serper_calls": 0})
                    except: pass
                
                if "Hunting" in status:
                    data["total_scans"] = (res_stats[0].get("total_scans") or 0) + 1
        
        # Dashboard Status Message Cleanup
        if status == "Sleeping 💤":
            status = "Sleeping 💤 | Waiting for GitHub Trigger"

        data["status"] = status
        # NUCLEAR PATCH: Straight to the point
        supabase_call("PATCH", "system_stats", data=data, params={"id": "eq.1"})
    except:
        logger.warning("⚠️ Status Heartbeat Blinked (but hunt continues)")

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
    
    # Step 1: Extract company name from discovery package
    company_name = discovery_package.split('|')[0].replace('Title:', '').strip()[:80]
    
    prompt = f"""
    ROLE: Senior UAE Market Intelligence Auditor.
    MISSION: Perform a deep verification audit on '{company_name}'.
    SIGNAL SOURCE: {discovery_package}

    AUDIT RULES:
    1. Use ALL your knowledge about this company. Do NOT just read the snippet.
    2. GCC ONLY: Must be a real UAE/Dubai/Abu Dhabi entity. If not, score: 0.
    3. NO Indian/Pakistani rupee companies. UAE-based only.
    4. ceo_founder: Give real name and role. Format: 'Name (Title)'. 
    5. financials: State actual funding round if known (e.g. $5M Series A, AED 2M seed). 
    6. registry_status: Check if registered in UAE registries:
       - DED Dubai (Dubai Economy & Tourism)  
       - DCAI (Dubai Chamber of AI)
       - ADBC Abu Dhabi Business Centre
       - DIFC (Dubai International Financial Centre)
       - WAM.ae (UAE State Registry)
       - "Active Entity - Master Registry" if confirmed active
       - "Financial Register - Verified" if funding is confirmed
       If unsure: "PROBING..."
    7. patron_chairman: UAE government patron or board chairman if known.
    8. integration_opportunity: Specific IT service they would need from an IT solutions vendor.
    9. RETURN JSON ONLY. No markdown.

    FORMAT:
    {{
        "company": "string",
        "industry": "string",
        "confidence_score": int (0-100, min 70 to pass),
        "strategic_signal": "string (1 sentence: what they are doing in UAE right now)",
        "integration_opportunity": "string (specific IT service opportunity)",
        "patron_chairman": "string",
        "ceo_founder": "string (Name and Role)",
        "financials": "string (exact funding amount or stage if known)",
        "registry_status": "string (UAE registry classification)"
    }}
    Not a UAE tech company or score below 70? Return: {{"confidence_score": 0}}
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
        
        if data.get("confidence_score", 0) < 70: return "SKIP"
        if not data.get("company"): return "SKIP"
        data["status"] = "Active" if data.get("confidence_score", 0) >= 85 else "Pending"
        return data
    except Exception as e:
        if "API key not valid" in str(e) or "400" in str(e):
            vault.mark_key_dead(key)
        logger.error(f"⚠️ Gemini Exhausted/Error: {e}")
        vault.rotate_gemini()
        # FALLBACK: GROQ
        groq_key = vault.get_groq_key()
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
                if conf < 70: return "SKIP"
                if not data.get("company"): return "SKIP"
                data["status"] = "Active" if conf >= 85 else "Pending"
                return data
            except Exception as ex:
                logger.error(f"❌ Groq Error: {ex}")
                vault.rotate_groq()
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
    # --- AGGRESSIVE DISCOVERY NICHES ---
    current_niches = [
        "site:crunchbase.com/organization UAE technology funding 2026",
        "site:apollo.io/companies Dubai technology hiring HQ",
        "Dubai tech startup expansion news last 48 hours",
        "Abu Dhabi AI Fintech investment rounds 2026",
        "Dubai Future Foundation accelerator companies",
        "DIFC Innovation Hub new company members",
        "site:linkedin.com/company UAE startup Hiring CEO Founder",
        "site:magniitt.com UAE venture capital funding"
    ]
    
    # Pick 2 niches based on the current hour to ensure a rotating variety every 24h
    hour = datetime.now(timezone.utc).hour
    selected_niches = [current_niches[hour % len(current_niches)], 
                       current_niches[(hour + 1) % len(current_niches)]]
                      
    for idx_n, niche in enumerate(selected_niches):
        source = niche.split(".")[1] if "." in niche else "Web"
        update_agent_status(f"Hunting 🔴 ({idx_n+1}/2: {source.title()} Scan)")
        logger.info(f"🚀 GLOBAL HARVEST: '{niche}'...")

        results = serper_search_broad(niche)
        
        for idx, item in enumerate(results):
            # Instant Kill Switch: Check if user paused via dashboard during the hunt
            if supabase and idx % 2 == 0:  # Check every 2 items to save API calls
                try:
                    res = supabase.table("system_stats").select("status").eq("id", 1).execute()
                    if res.data and res.data[0].get("status") == "Paused ⏸️":
                        logger.warning("🛑 INSTANT KILL SWITCH ACTIVATED: Hunt aborted by user.")
                        return
                except: pass

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
