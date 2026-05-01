import os
import time
import json
import logging
import requests
import csv
import re
from datetime import datetime, timezone
from duckduckgo_search import DDGS
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
        
        gemini_env = os.getenv("GEMINI_API_KEYS", "") or os.getenv("GEMINI_API_KEY", "")
        groq_env = os.getenv("GROQ_API_KEYS", "") or os.getenv("GROQ_API_KEY", "")
        serper_env = os.getenv("SERPER_API_KEYS", "") or os.getenv("SERPER_API_KEY", "")
        
        self.gemini_keys = [k.strip() for k in gemini_env.split(",") if k.strip()] or self.config.get("GEMINI_API_KEYS", [])
        self.groq_keys = [k.strip() for k in groq_env.split(",") if k.strip()] or self.config.get("GROQ_API_KEYS", [])
        self.serper_keys = [k.strip() for k in serper_env.split(",") if k.strip()] or self.config.get("SERPER_API_KEYS", [])
        
        self.gemini_idx = 0
        self.groq_idx = 0
        self.serper_idx = 0
        self.dead_keys = set()

    def reset_daily(self):
        self.dead_keys = set()
        logger.info("🌤️ TOKEN SELF-HEALING: New day detected. All Gemini/Groq keys refreshed.")

    def get_gemini_key(self):
        if not self.gemini_keys: return None
        for _ in range(len(self.gemini_keys)):
            key = self.gemini_keys[self.gemini_idx % len(self.gemini_keys)]
            if key not in self.dead_keys: return key
            self.gemini_idx += 1
        return None

    def mark_key_dead(self, key):
        self.dead_keys.add(key)
        logger.warning(f"💀 KEY BLACKLISTED: {key[:8]}... marked as dead/invalid.")

    def get_serper_key(self):
        if not self.serper_keys: return None
        key = self.serper_keys[self.serper_idx % len(self.serper_keys)]
        self.serper_idx += 1
        return key

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
                        # We keep Gemini/Groq cumulative or session-based (Transparency Fix)
                        pass
                    except: pass
                
                if "Hunting" in status:
                    data["total_scans"] = (res_stats[0].get("total_scans") or 0) + 1
        
        # Dashboard Status Message Cleanup
        if status == "Sleeping 💤":
            status = "Sleeping 💤 | Waiting for GitHub Trigger"

        data["status"] = status
        # NUCLEAR PATCH: Straight to the point
        supabase_call("PATCH", "system_stats", data=data, params={"id": "eq.1"})
        
        # Incremental Heartbeat: One scan happened
        res = supabase_call("GET", "system_stats", params={"id": "eq.1", "select": "total_scans,today_scans,last_run_at"})
        if res:
            stats = res[0]
            total_s = (stats.get("total_scans") or 0) + 1
            today_s = (stats.get("today_scans") or 0) + 1
            
            # Smart Reset: If last_run_at day is different from now, reset today count to 1
            last_run_at = stats.get("last_run_at")
            if last_run_at:
                try:
                    last_dt = datetime.fromisoformat(last_run_at.replace("Z", "+00:00"))
                    if last_dt.day != now.day or last_dt.month != now.month:
                        today_s = 1
                except: pass
                
            supabase_call("PATCH", "system_stats", 
                          data={"total_scans": total_s, "today_scans": today_s, "last_run_at": now.isoformat()}, 
                          params={"id": "eq.1"})
    except:
        logger.warning("⚠️ Status Heartbeat Blinked (but hunt continues)")

def save_to_csv(lead):
    """Saves lead to local CSV backup matching your format."""
    file_exists = os.path.exists(CSV_FILE)
    headers = ["Confidence", "Company", "Industry", "Patron/Chairman", "CEO/Founder", "Funding Amount", "Funding Round", "Financials", "2026 Strategic Signal", "Integration Opportunity", "Registry Status", "URL", "Discovered At"]
    
    # Deduplication check
    if file_exists:
        try:
            with open(CSV_FILE, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("Company") == lead.get("company"):
                        return # Skip duplicate
        except Exception: pass

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
                "Funding Amount": lead.get("funding_amount", "Undisclosed"),
                "Funding Round": lead.get("funding_round", "Unknown Round"),
                "Financials": lead.get("financials"),
                "2026 Strategic Signal": lead.get("strategic_signal"),
                "Integration Opportunity": lead.get("integration_opportunity"),
                "Registry Status": lead.get("registry_status"),
                "URL": lead.get("url"),
                "Discovered At": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            })
    except Exception as e:
        logger.error(f"❌ CSV Backup Error: {e}")

def clean_company_name(raw_name):
    """Deep scrubber to isolate company names and kill news headlines."""
    if not raw_name: return "Unknown Entity"
    
    # 1. Reject Garbage Entities (Chambers, Governments, Big Tech)
    rejection_keywords = [
        'chamber', 'authority', 'government', 'park', 'ministry', 'department', 
        'council', 'centre', 'center', 'university', 'college', 'school',
        'openai', 'google', 'meta', 'microsoft', 'amazon', 'apple',
        'summit', 'conference', 'workshop', 'exhibition', 'festival'
    ]
    if any(k in raw_name.lower() for k in rejection_keywords):
        return "FILTERED_GARBAGE"

    # 2. Extract pure company name (usually before the first dash or pipe)
    clean = re.split(r' \-| \| | \/ | \.\.\.|\: ', raw_name)[0]
    
    # 3. Strip web site suffixes
    clean = re.sub(r'Crunchbase|LinkedIn|Apollo\.io|Instagram|Facebook|Twitter|YouTube|TikTok|WAM\.ae|Reuters|Bloomberg|News', '', clean, flags=re.I)
    
    # 4. Clean non-alphanumeric at ends
    clean = re.sub(r'^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$', '', clean).strip()
    
    # 5. FINAL SAFETY: Name should be 1-4 words usually
    if len(clean.split()) > 5:
        return "FILTERED_HEADLINE"
        
    return clean.strip()

def extract_funding_regex(company, context):
    """Zero-Quota math-based extraction. Matches Crunchbase text directly."""
    amount = "Undisclosed"
    round_name = "Unknown Round"
    
    # Match amounts: $5M, $2.5 million, AED 10M, USD 100M etc.
    amt_patterns = [
        r'\$([\d\.]+)\s*(billion|million|B|M|bn|mn)',
        r'([\d\.]+)\s*(billion|million)\s*(?:USD|AED|dollars?)',
        r'AED\s*([\d\.]+)\s*(billion|million|B|M|bn|mn)',
        r'USD\s*([\d\.]+)\s*(billion|million|B|M|bn|mn)',
        r'raised\s+\$?([\d\.]+)\s*(billion|million|B|M)',
        r'secured\s+\$?([\d\.]+)\s*(billion|million|B|M)',
    ]
    for pattern in amt_patterns:
        match = re.search(pattern, context, re.IGNORECASE)
        if match:
            num = match.group(1); unit = match.group(2).upper()
            if unit in ['MILLION', 'M', 'MN']: unit = 'M'
            elif unit in ['BILLION', 'B', 'BN']: unit = 'B'
            amount = f"${num}{unit}"
            break
            
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
        (r'acquisition|m\&a|merged|bought.*by', 'M&A / Acquisition'),
        (r'debt\s+financing|loan|credit\s+facility', 'Debt'),
        (r'angel\s+round|angel\s+investment', 'Angel'),
        (r'grant|award|prize', 'Grant'),
        (r'series\s+[\w]+', 'Series Unknown'),
    ]
    for pattern, label in round_patterns:
        if re.search(pattern, context, re.IGNORECASE):
            round_name = label
            break
            
    return {"amount": amount, "round": round_name, "summary": context[:180].strip() if context else "Found via discovery."}

def compile_auditor_intel_extreme(discovery_package):
    """High-Volume Gemini 2.0 extraction maximized for 3000 leads daily."""
    key = vault.get_gemini_key()
    if not key: return "SKIP"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
    
    # Step 1: Extract and CLEAN company name from discovery package
    company_name = clean_company_name(discovery_package.split('|')[0].replace('Title:', '').strip()[:100])
    if company_name == "FILTERED_HEADLINE":
        return "SKIP"
    
    prompt = f"""    ROLE: Hyper-Scale UAE Lead Generation Agent in April 2026.
    MISSION: Identify private startup funding rounds from the following search result:
    {discovery_package}
    
    AUDIT RULES:
    1. STARTUP FOCUS: Only accept private companies (Seed, Series A, Venture, etc.).
    2. REJECT: Government, Large Corporates (>1000 employees), Non-Profits.
    3. UAE ONLY: Must be headquartered or have significant operations in UAE.
    4. DATE: Last 30-90 days is acceptable.
    
    RETURN JSON ONLY: {{"company": "Name", "industry": "Industry", "confidence_score": 0-100, "strategic_signal": "Description", "funding_amount": "Amount", "funding_round": "Round", "funding_date": "Month Year (e.g. April 2026)", "ceo_founder": "Name", "integration_opportunity": "IT Need"}}
    If not a UAE startup? Return: {{"confidence_score": 0}}"""
    
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
        # If we have more than 1 Gemini key, we could retry, but switching to Groq is safer for extraction
        
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
    
    # --- NUCLEAR FALLBACK: If Gemini fails, use Groq specifically for name extraction + Regex for funding ---
    logger.info(f"🛡️ NUCLEAR FALLBACK: Extracting via Groq/Regex for {company_name}")
    
    refined_name = company_name
    groq_key = vault.get_groq_key()
    if groq_key:
        try:
            client_groq = Groq(api_key=groq_key)
            name_check = client_groq.chat.completions.create(
                messages=[{"role": "user", "content": f"Extract ONLY the company name from this title: '{discovery_package.split('|')[0]}'. Return just the name, NO commentary."}],
                model="llama-3.1-8b-instant"
            )
            refined_name = clean_company_name(name_check.choices[0].message.content.strip())
            if refined_name == "FILTERED_HEADLINE": return "SKIP"
        except: pass

    regex_data = extract_funding_regex(refined_name, discovery_package)
    return {
        "company": refined_name,
        "industry": "Tech/Innovation",
        "confidence_score": 80,
        "strategic_signal": regex_data["summary"],
        "integration_opportunity": "Advanced IT / AI Solutions",
        "patron_chairman": "TBD",
        "ceo_founder": "Founding Team",
        "funding_amount": regex_data["amount"],
        "funding_round": regex_data["round"],
        "financials": regex_data["summary"],
        "registry_status": "Live Discovery",
        "status": "Pending"
    }



def gemini_discovery_grounded(query):
    """Triple-Layer Discovery: Serper -> Gemini Grounding -> DuckDuckGo."""
    
    # LAYER 1: SERPER (Most accurate for Crunchbase)
    serper_key = vault.get_serper_key()
    if serper_key:
        logger.info(f"🔍 SERPER SEARCH: '{query}'...")
        try:
            track_cloud_usage("Serper")
            r = requests.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": serper_key, "Content-Type": "application/json"},
                json={"q": f"site:crunchbase.com {query} UAE hiring", "num": 10},
                timeout=10
            )
            res = r.json()
            if "organic" in res:
                logger.info(f"✅ Serper found {len(res['organic'])} results.")
                return res["organic"]
        except Exception as e:
            logger.warning(f"Serper search failed: {e}")

    # LAYER 2: GEMINI GROUNDING
    logger.info(f"💎 GEMINI GROUNDING: '{query}'...")
    prompt = f"""
    You are an IT Market Intelligence Agent. Search for 5-10 NEW tech startups or IT companies in the UAE 
    that match this sector: '{query}'. 
    Specifically look for Crunchbase profiles, funding news, or official company hiring pages.
    
    Return a JSON array of objects:
    [{{ "title": "Company Name | Signal", "link": "Crunchbase URL", "snippet": "Description of hiring or funding" }}]
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search_retrieval": {}}],
        "generationConfig": {"response_mime_type": "application/json"}
    }
    
    for _ in range(len(vault.gemini_keys) or 1): # Try all available keys
        key = vault.get_gemini_key()
        if not key:
            logger.error("No Gemini keys available for discovery!")
            return []
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
        try:
            track_cloud_usage("Gemini")
            r = requests.post(url, json=payload, timeout=30)
            data = r.json()
            if 'error' in data:
                if data['error'].get('code') in [429, 403, 400]:
                    logger.warning(f"⚠️ Gemini Discovery Quota Hit: Rotating Key...")
                    vault.rotate_gemini()
                    continue # Retry with next key
            elif 'candidates' in data:
                text = data['candidates'][0]['content']['parts'][0]['text']
                clean_text = re.sub(r'```json\s*|\s*```', '', text).strip()
                return json.loads(clean_text)
    # FALLBACK: If Gemini Grounding is hit, use DuckDuckGo + Gemini Extraction
    logger.info(f"🔄 FALLBACK: Using DuckDuckGo for '{query}'...")
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(f"site:crunchbase.com {query} UAE hiring", max_results=10))
            if results:
                formatted = [{"title": r.get("title", ""), "link": r.get("href", ""), "snippet": r.get("body", "")} for r in results]
                logger.info(f"✅ DuckDuckGo found {len(formatted)} results.")
                return formatted
    except Exception as e:
        logger.error(f"⚠️ DuckDuckGo Fallback Failed: {e}")
    return []


def run_tracker():
    # --- DAILY INTELLIGENCE SYNC ---
    now = datetime.now(timezone.utc)
    try:
        stats_res = supabase.table("system_stats").select("*").eq("id", 1).execute()
        if stats_res.data:
            stats = stats_res.data[0]
            last_run_str = stats.get("last_run_at")
            if last_run_str:
                last_dt = datetime.fromisoformat(last_run_str.replace('Z', '+00:00'))
                # Reset if it's a new day (UTC)
                if last_dt.date() < now.date():
                    logger.info("🌤️ NEW DAY DETECTED: Resetting Daily Stats for the new hunt cycle...")
                    vault.reset_daily()
                    supabase.table("system_stats").update({
                        "today_scans": 0,
                        "today_leads": 0,
                        "last_run_at": now.isoformat()
                    }).eq("id", 1).execute()
                    logger.info("✅ Daily stats successfully zeroed out for 12 AM refresh.")
    except Exception as e:
        logger.error(f"Daily Sync Error: {e}")

    # 1. Smart Overlap & Pause Protection
    num_niches_to_scan = 12 # Reduced to respect Gemini free-tier RPM limits
    update_agent_status("Hunting Leads 🎯")
    
    # 2. THE ULTIMATE HUNT: Combining Live Pulse + Deep History
    current_niches = [
        "Software Development Hiring Dubai",
        "SaaS startups Abu Dhabi hiring",
        "FinTech developers UAE",
        "AI Research Engineers Dubai",
        "Cloud Infrastructure hiring UAE",
        "Cybersecurity startups Dubai",
        "Web3 developers Abu Dhabi",
        "E-commerce tech teams UAE",
        "IT Managed Services hiring Dubai",
        "Data Science startups UAE"
    ]
    
    import random
    random.shuffle(current_niches)

    if supabase:
        try:
            res = supabase.table("system_stats").select("status,last_run_at").eq("id", 1).execute()
            if res.data:
                current_status = res.data[0].get("status")
                if current_status == "Paused ⏸️":
                    logger.info("Agent is manually paused. Skipping hunt.")
                    return
                if "Hunting" in current_status:
                    logger.info("🛡️ OVERLAP PREVENTION: Another hunt is active. We will STILL run auto-resurrection check before skipping.")
                    pass # TEMPORARY: allow it to pass through to resurrection
                
                # 2. Catch-Up Logic: If gap > 40 mins, double the harvest
                last_run_at = res.data[0].get("last_run_at")
                if last_run_at:
                    last_dt = datetime.fromisoformat(last_run_at.replace("Z", "+00:00"))
                    gap_mins = (datetime.now(timezone.utc) - last_dt).total_seconds() / 60
                    if gap_mins > 40:
                        pass
        except:
            pass

    # --- DEEP AUTO-RESURRECTION DISABLED ---

    # --- ATOMIC VELOCITY BOOST ---
    num_niches_to_scan = 60
    logger.info(f"🚀 ATOMIC VELOCITY: Scanning {num_niches_to_scan} niches to restore lead volume!")

    # Remnant block removed to prevent double execution.

    # --- RETROACTIVE CLEANUP: Fix garbage and Purge KNOWN News ---
    try:
        logger.info("🧹 RETROACTIVE CLEANUP: Purging confirmed news junk...")
        res = supabase.table("uae_leads").select("id, company, url").execute()
        for item in res.data:
            old_name = item.get("company", "")
            url = item.get("url", "")
            cleaned = clean_company_name(old_name)
            
            # PURGE IF:
            # 1. Headline detected
            # 2. URL is a known news site (not just 'not Crunchbase')
            # 3. Name is garbage/too long
            if cleaned == "FILTERED_HEADLINE" or any(news in (url or "").lower() for news in ['wam.ae', 'reuters', 'bloomberg', 'news.']) or len(old_name) > 60:
                # supabase.table("uae_leads").delete().eq("id", item["id"]).execute()
                logger.info(f"⚠️ Flagged Bad Entry (Skipping for safety): {old_name[:30]}...")
            elif cleaned != old_name:
                supabase.table("uae_leads").update({"company": cleaned}).eq("id", item["id"]).execute()
                logger.info(f"✨ Cleaned: {old_name[:20]} -> {cleaned}")
    except Exception as e:
        logger.warning(f"Cleanup skip: {e}")

    # --- CRUNCHBASE TIME MACHINE: Historical Funding Rounds (April 14 - Now) ---
    current_niches = [
        "Software Development Hiring Dubai",
        "SaaS startups Abu Dhabi hiring",
        "FinTech developers UAE",
        "AI Research Engineers Dubai",
        "Cloud Infrastructure hiring UAE",
        "Cybersecurity startups Dubai",
        "Web3 developers Abu Dhabi",
        "E-commerce tech teams UAE",
        "IT Managed Services hiring Dubai",
        "Data Science startups UAE"
    ]
    
    # Pick niches based on the current hour and catch-up requirement
    hour = datetime.now(timezone.utc).hour
    selected_niches = []
    for i in range(num_niches_to_scan):
        idx = (hour + i) % len(current_niches)
        selected_niches.append(current_niches[idx])
                      
    for idx_n, niche in enumerate(selected_niches):
        source = niche.split(".")[1] if "." in niche else "Web"
        update_agent_status(f"Hunting 🔴 ({idx_n+1}/{num_niches_to_scan}: {source.title()} Scan)")
        logger.info(f"🚀 GLOBAL HARVEST: '{niche}'...")

        results = gemini_discovery_grounded(niche)
        
        for idx, item in enumerate(results):
            time.sleep(6) # Adhere to Gemini 10 RPM (60s/10)
            # Instant Kill Switch: Check if user paused via dashboard during the hunt
            if supabase and idx % 2 == 0:  # Check every 2 items to save API calls
                try:
                    res = supabase.table("system_stats").select("status").eq("id", 1).execute()
                    if res.data and res.data[0].get("status") == "Paused ⏸️":
                        logger.warning("🛑 INSTANT KILL SWITCH ACTIVATED: Hunt aborted by user.")
                        return
                except: pass

            # --- SOURCE FILTER ---
            link = item.get('link', '').lower()
            # We prefer Crunchbase, but allow news/official sites since Serper is gone
            if not any(valid in link for valid in ['crunchbase.com', 'linkedin.com', 'wam.ae', 'zawya.com', 'menabytes.com']):
                # If it's a direct company site (.ae, .com), we allow it too
                if not (link.endswith('.ae') or link.endswith('.com')):
                    continue
            
            # Block known garbage
            if any(bad in link for bad in ['/blog/', '/news/', '/lists/', '/hub/', '/search/', '/investor/', '/person/', '/event/']):
                if 'crunchbase.com' in link: # Only block these if on Crunchbase
                    continue
            logger.info(f"  ✅ Valid Crunchbase profile: {link[:80]}")
                
            discovery_package = f"Title: {item.get('title')} | Snippet: {item.get('snippet')} | URL: {link}"
            
            # --- SMART FILTER: Prevent Wasting AI Credits on Existing Leads ---
            if supabase:
                try:
                    # check by URL or Title to avoid AI costs for items we already found
                    existing = supabase.table("uae_leads").select("id").or_(f"url.eq.{link},company.ilike.%{item.get('title','UNKNOWN')[:15]}%").execute()
                    if existing.data:
                        continue # Already in HQ, save Gemini call
                except: pass

            intel = compile_auditor_intel_extreme(discovery_package)
            
            if isinstance(intel, dict) and intel.get("company"):
                intel['url'] = item.get('link')
                intel['discovered_at'] = datetime.now(timezone.utc).isoformat()
                
                # --- DUAL STORAGE: Supabase + CSV ---
                if supabase:
                    try:
                        supabase.table("uae_leads").upsert(intel, on_conflict="company").execute()
                        # Direct increment of today_leads in system_stats
                        res = supabase.table("system_stats").select("today_leads").eq("id", 1).execute()
                        if res.data:
                            new_leads = (res.data[0].get("today_leads") or 0) + 1
                            supabase.table("system_stats").update({"today_leads": new_leads}).eq("id", 1).execute()
                    except Exception as e:
                        logger.error(f"❌ DB Error during lead save: {e}")
                save_to_csv(intel)
                logger.info(f"✅ HARVESTED: {intel['company']} (Cloud + Local CSV)")

if __name__ == "__main__":
    try:
        run_tracker()
    finally:
        update_agent_status("Sleeping 💤 | Watching 24/7 Trigger")
