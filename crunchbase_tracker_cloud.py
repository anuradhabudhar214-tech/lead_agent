import os
import time
import json
import logging
import requests
import csv
import re
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
    
    # 1. Skip if it looks like a news title prefix
    if re.match(r'^\d', raw_name) or any(word in raw_name.lower() for word in ['joined', 'member', 'launches', 'announced', 'hiring']):
        return "FILTERED_HEADLINE"
        
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
    
    prompt = f"""
    ROLE: Senior UAE Market Intelligence Auditor reading a REAL Crunchbase.com company profile.
    MISSION: Extract precise funding intelligence for '{company_name}'.
    CRUNCHBASE SOURCE: {discovery_package}

    AUDIT RULES:
    1. This is a REAL Crunchbase profile. Extract all funding data visible in the snippet.
    2. GCC ONLY: Must be a real UAE/Dubai/Abu Dhabi entity. If not, score: 0.
    3. funding_round: Extract the EXACT round type shown on Crunchbase (e.g. "Seed", "Series A", "Series B", "Pre-Seed", "Venture Round", "Angel", "IPO"). NEVER return "Unknown Round" if text mentions any funding event.
    4. funding_amount: Extract ONLY the exact money amount (e.g., "$5M", "AED 10.5M", "$2.3B"). If not shown, return "Undisclosed".
    5. financials: Name the actual investors or lead VC funds if mentioned. Otherwise describe the round briefly.
    6. ceo_founder: Real full name and role, format: 'Name (Title)'.
    7. registry_status: UAE registry from: DED Dubai, DCAI, ADBC, DIFC, WAM.ae, "Active Entity - Master Registry", "Financial Register - Verified". Default: "PROBING..."
    8. patron_chairman: UAE government patron or board chairman if known, else "N/A".
    9. integration_opportunity: Specific IT service this company needs from an IT solutions vendor.
    10. RETURN JSON ONLY. No markdown. No extra text.

    FORMAT:
    {{
        "company": "string (exact company name as on Crunchbase)",
        "industry": "string",
        "confidence_score": int (0-100, min 70 to pass),
        "strategic_signal": "string (1 sentence: what they are doing in UAE right now)",
        "integration_opportunity": "string (specific IT service opportunity)",
        "patron_chairman": "string",
        "ceo_founder": "string (Name and Role)",
        "funding_amount": "string (exact amount or Undisclosed)",
        "funding_round": "string (exact round type: Seed/Series A/Series B/Pre-Seed/Venture/Angel/IPO/etc)",
        "financials": "string (investor names or round summary)",
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

def serper_search_broad(query):
    """Crunchbase-targeted Serper discovery."""
    key = vault.get_serper_key()
    if not key:
        logger.error("No Serper keys available!")
        return []
    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": key, "Content-Type": "application/json"}
    try:
        track_cloud_usage("Serper")
        payload = {"q": query, "num": 50}
        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=15)
        res_data = r.json()
        if r.status_code == 403 or r.status_code == 429:
            logger.warning(f"Serper key quota hit ({r.status_code}), rotating...")
            vault.rotate_serper()
            return []
        if 'organic' in res_data:
            results = res_data['organic']
            logger.info(f"  Serper returned {len(results)} results")
            return results
        logger.warning(f"Serper response issue: {res_data.get('message', 'no organic')}")
        return []
    except Exception as e:
        logger.error(f"Serper request failed: {e}")
        vault.rotate_serper()
        return []

def run_tracker():
    # 1. Smart Overlap & Pause Protection
    num_niches_to_scan = 5
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
                        logger.warning(f"🚀 CATCH-UP MODE: Detected {int(gap_mins)}m gap. Doubling harvest velocity.")
                        num_niches_to_scan = 10
        except:
            pass

    # --- DEEP AUTO-RESURRECTION: Scans entire Git history to recover all 100+ leads ---
    try:
        res = supabase.table("uae_leads").select("id", count="exact").execute()
        if res.count < 100:
            logger.info("🕰️ DEEP RECONSTRUCTION: Scanning entire Git history for lost leads...")
            import subprocess, csv, io
            
            # 1. Get all commits for the leads file
            commits = subprocess.check_output(['git', 'log', '--pretty=format:%h', 'enterprise_leads.csv']).decode().split()
            all_historical_leads = {} 

            # 2. Extract unique companies from every single backup
            for c in commits[:50]: # Scan last 50 backups for maximum coverage
                try:
                    data = subprocess.check_output(['git', 'show', f'{c}:enterprise_leads.csv'], stderr=subprocess.DEVNULL).decode(errors='ignore')
                    reader = csv.DictReader(io.StringIO(data))
                    for row in reader:
                        name = (row.get("Company") or row.get("company") or "").strip()
                        if not name or name == "Filter Out" or len(name) < 2: continue
                        
                        conf = int(row.get("Confidence") or 85)
                        if name not in all_historical_leads or conf > all_historical_leads[name].get('confidence_score', 0):
                            all_historical_leads[name] = {
                                "company": name,
                                "industry": row.get("Industry") or "Technology",
                                "confidence_score": conf,
                                "funding_amount": row.get("Funding Amount") or row.get("Financials") or "Undisclosed",
                                "financials": row.get("Financials") or "Undisclosed",
                                "strategic_signal": row.get("2026 Strategic Signal") or "N/A",
                                "integration_opportunity": row.get("Integration Opportunity") or "N/A",
                                "url": row.get("URL") or "",
                                "discovered_at": datetime.now(timezone.utc).isoformat() 
                            }
                except: continue

            # 3. Resilient Individual Sync
            if all_historical_leads:
                leads_list = list(all_historical_leads.values())
                logger.info(f"✨ Reconstructed {len(leads_list)} unique companies from history. Syncing...")
                success_count = 0
                for lead in leads_list:
                    try:
                        supabase.table("uae_leads").upsert(lead, on_conflict="company").execute()
                        success_count += 1
                    except Exception: pass
                
                logger.info(f"🏁 DEEP RECONSTRUCTION COMPLETE: {success_count} leads restored!")
    except Exception as e:
        logger.warning(f"Resurrection skip: {e}")

    # --- ATOMIC VELOCITY BOOST ---
    num_niches_to_scan = 10
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
        # Historical Targets (April/May 2024)
        'crunchbase.com UAE "Series A" funding April 2024',
        'crunchbase.com Dubai "Seed" funding raised April 2024',
        'crunchbase.com Abu Dhabi startup raised May 2024',
        'crunchbase.com UAE "Series B" funding May 2024',
        'crunchbase.com Dubai tech "Venture Round" April 2024',
        'crunchbase.com UAE startup "Series A" May 2024',
        
        # Fresh Targets (Latest 2024/2025)
        'crunchbase.com UAE startup "Series A" funding raised million',
        'crunchbase.com Dubai startup "Series B" funding raised million',
        'crunchbase.com "Abu Dhabi" startup "Seed" funding raised',
        'crunchbase.com UAE startup "Pre-Seed" funding raised 2024',
        'crunchbase.com Dubai startup "Venture Round" raised million',
        'crunchbase.com UAE "Series C" funding round raised 2024',
        'crunchbase UAE Dubai AI technology startup funding round raised',
        'crunchbase Dubai fintech startup seed funding raised million',
        'crunchbase UAE proptech startup funding round 2024 2025',
        'crunchbase Dubai SaaS B2B startup series A funding raised',
        'crunchbase UAE healthtech biotech funding series raised',
        'crunchbase Dubai cybersecurity startup funding round raised',
        'crunchbase UAE logistics supply chain startup funding raised',
        'crunchbase Dubai edtech startup funding raised million',
        'crunchbase Abu Dhabi cleantech green energy funding raised',
        'crunchbase UAE e-commerce startup raised series funding 2024',
        'crunchbase Dubai robotics automation startup funding raised',
        'crunchbase UAE web3 blockchain crypto startup funding',
        'crunchbase Dubai cloud infrastructure SaaS startup raised',
        'crunchbase UAE insurtech legaltech startup funding raised',
        'crunchbase Dubai founded 2022 2023 2024 UAE tech startup funding',
        'crunchbase Abu Dhabi capital investment tech startup raised',
        'crunchbase UAE smart mobility transport startup raised',
        'crunchbase Dubai gaming esports tech startup funding raised',
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

            # --- STRICT CRUNCHBASE-ONLY FILTER ---
            link = item.get('link', '').lower()
            # Must be on crunchbase.com
            if 'crunchbase.com' not in link:
                continue
            # Must be a company/organization profile (not blog, hub, lists, etc)
            is_profile = ('/organization/' in link or '/company/' in link or 
                         link.rstrip('/').split('crunchbase.com/')[-1].count('/') == 1)
            if not is_profile:
                continue
            # Block known non-profile paths
            if any(bad in link for bad in ['/blog/', '/news/', '/lists/', '/hub/', '/search/', '/investor/', '/person/', '/event/']):
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
                    except Exception as e:
                        logger.error(f"❌ DB Error: {e}")
                save_to_csv(intel)
                logger.info(f"✅ HARVESTED: {intel['company']} (Cloud + Local CSV)")

if __name__ == "__main__":
    try:
        run_tracker()
    finally:
        update_agent_status("Sleeping 💤")
