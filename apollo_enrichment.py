import os
import time
import requests
import json
import logging
import re
from supabase import create_client, Client

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GEMINI_API_KEYS_STR = os.environ.get("GEMINI_API_KEYS", os.environ.get("GEMINI_API_KEY", ""))
SERPER_API_KEYS_STR = os.environ.get("SERPER_API_KEYS", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("Supabase credentials missing.")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
gemini_keys = [k.strip() for k in GEMINI_API_KEYS_STR.split(",") if k.strip()]
serper_keys = [k.strip() for k in SERPER_API_KEYS_STR.split(",") if k.strip()]
gemini_idx = 0
serper_idx = 0

def get_gemini_key():
    global gemini_idx
    if not gemini_keys: return None
    key = gemini_keys[gemini_idx % len(gemini_keys)]
    gemini_idx += 1
    return key

def get_serper_key():
    global serper_idx  
    if not serper_keys: return None
    key = serper_keys[serper_idx % len(serper_keys)]
    serper_idx += 1
    return key

def search_serper(query):
    """Use Serper to search web for person's info."""
    key = get_serper_key()
    if not key: return []
    try:
        r = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": key, "Content-Type": "application/json"},
            json={"q": query, "num": 5},
            timeout=10
        )
        return r.json().get("organic", [])
    except:
        return []

def ask_gemini_for_contact(company_name, company_context=""):
    """Ask Gemini to find CEO/CTO name and the email for a company via web search."""
    key = get_gemini_key()
    if not key: return None
    
    prompt = f"""You are a B2B contact researcher. Search the web deeply and find:
    1. The CEO, CTO, Founder, or VP Engineering of company: "{company_name}"
    2. Their real verified work email address
    
    Context about the company: {company_context}
    
    Search their official website (About, Team, Contact pages), LinkedIn, Crunchbase, press releases.
    
    Return ONLY a JSON object (no markdown, no extra text) in this format:
    {{"name": "Full Name", "role": "CEO", "email": "name@company.com", "confidence": "high/medium/low"}}
    
    If no verified email found, return: {{"name": "Name if found", "role": "Role if found", "email": "not_found", "confidence": "low"}}
    """
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 256}
    }
    
    try:
        r = requests.post(url, json=payload, timeout=20)
        if r.status_code == 429:
            logger.warning("Gemini quota hit, retrying with next key.")
            key = get_gemini_key()
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
            r = requests.post(url, json=payload, timeout=20)
        
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        # Strip markdown code fences if present
        text = re.sub(r"```json|```", "", text).strip()
        data = json.loads(text)
        return data
    except Exception as e:
        logger.warning(f"Gemini contact search failed: {e}")
        return None

def guess_email_format(name, domain):
    """Generate common email format guesses based on name and domain."""
    if not name or not domain: return []
    parts = name.lower().split()
    if len(parts) < 2: return [f"{parts[0]}@{domain}"]
    first, last = parts[0], parts[-1]
    return [
        f"{first}.{last}@{domain}",
        f"{first[0]}{last}@{domain}",
        f"{first}@{domain}",
        f"{first}_{last}@{domain}",
    ]

def run_enrichment():
    logger.info("=== Contact Enrichment Engine v3 (Serper-First) Starting ===")
    
    # Fetch any leads missing contact email
    res = supabase.table("uae_leads").select("*").is_("contact_email", "null").limit(8).execute()
    leads = res.data
    
    if not leads:
        logger.info("No leads require enrichment right now.")
        return
        
    logger.info(f"Targeting {len(leads)} leads for contact enrichment...")
    
    for lead in leads:
        company = lead.get("company", "")
        lead_id = lead.get("id")
        found_email = None
        found_name = None
        found_role = None
        
        logger.info(f"Searching contacts for: {company}")
        
        # STRATEGY 1: Serper - direct email extraction from web search
        queries = [
            f'"{company}" CEO email site:linkedin.com OR site:crunchbase.com',
            f'"{company}" founder CTO email UAE contact',
            f'"{company}" "@" CEO OR founder OR CTO UAE',
        ]
        
        for query in queries:
            results = search_serper(query)
            for result in results:
                snippet = result.get("snippet", "") + " " + result.get("title", "")
                email_match = re.search(r'[\w.+-]+@[\w-]+\.[a-z]{2,4}', snippet)
                if email_match:
                    found_email = email_match.group(0)
                    logger.info(f"Email found via Serper: {found_email}")
                    break
            if found_email:
                break
        
        # STRATEGY 2: Gemini fallback with strict JSON prompt
        if not found_email:
            contact = ask_gemini_for_contact(company, lead.get("strategic_signal", ""))
            if contact:
                found_name = contact.get("name")
                found_role = contact.get("role")
                email = contact.get("email", "")
                if email and email != "not_found" and "@" in email:
                    found_email = email
        
        # Write result to Supabase
        if found_email:
            logger.info(f"SUCCESS: {company} -> {found_email}")
            supabase.table("uae_leads").update({
                "contact_name": found_name,
                "contact_email": found_email,
                "contact_role": found_role
            }).eq("id", lead_id).execute()
        else:
            logger.info(f"No email found for {company} - marking as Not Found")
            supabase.table("uae_leads").update({"contact_email": "Not Found"}).eq("id", lead_id).execute()
            
        time.sleep(2)
pectful pacing

if __name__ == "__main__":
    run_enrichment()
    logger.info("=== Enrichment Cycle Complete ===")
