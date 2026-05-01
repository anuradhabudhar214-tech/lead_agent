import os
import requests
import json
import logging
import time
from datetime import datetime, timezone
from supabase import create_client, Client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GEMINI_API_KEYS_STR = os.environ.get("GEMINI_API_KEYS", "") or os.environ.get("GEMINI_API_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("Supabase credentials missing.")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
gemini_keys = [k.strip() for k in GEMINI_API_KEYS_STR.split(",") if k.strip()]
gemini_idx = 0

def get_gemini_key():
    global gemini_idx
    if not gemini_keys: return None
    key = gemini_keys[gemini_idx % len(gemini_keys)]
    gemini_idx += 1
    return key

def track_cloud_usage(api_name):
    try:
        col = f"{api_name.lower()}_calls"
        res = supabase.table("system_stats").select(f"id, {col}").eq("id", 1).execute()
        if res.data:
            new_val = (res.data[0].get(col) or 0) + 1
            supabase.table("system_stats").update({col: new_val}).eq("id", 1).execute()
    except: pass

def ask_gemini_grounded(prompt):
    """Reliable Gemini Grounded Search."""
    for _ in range(len(gemini_keys) or 1):
        key = get_gemini_key()
        if not key: break
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "tools": [{"google_search_retrieval": {}}],
            "generationConfig": {"response_mime_type": "application/json"}
        }
        
        try:
            track_cloud_usage("Gemini")
            r = requests.post(url, json=payload, timeout=20)
            res_data = r.json()
            if 'error' in res_data:
                if res_data['error'].get('code') in [429, 403]:
                    logger.warning("Gemini quota hit, rotating.")
                    continue
                return None
            
            text = res_data['candidates'][0]['content']['parts'][0]['text'].strip()
            return json.loads(text)
        except Exception as e:
            logger.warning(f"Gemini Grounded Search failed: {e}")
            continue
    return None

def enrich_lead(lead_id, company_name):
    """Finds decision maker LinkedIn and potential email patterns."""
    logger.info(f"🔎 Enriching: {company_name}")
    
    prompt = f"Find the Full Name and LinkedIn profile of the CEO, Founder, or Managing Director of {company_name} in the UAE. Return ONLY JSON: {{'contact_name': 'Name', 'contact_linkedin': 'URL', 'contact_role': 'Title'}}"
    
    contact_data = ask_gemini_grounded(prompt)
    if not contact_data:
        return
    
    # Update lead in DB
    try:
        supabase.table("uae_leads").update({
            "contact_name": contact_data.get("contact_name"),
            "contact_linkedin": contact_data.get("contact_linkedin"),
            "contact_role": contact_data.get("contact_role", "Founder/CEO"),
            "registry_status": "ENRICHED (Gemini Grounding)"
        }).eq("id", lead_id).execute()
        logger.info(f"✅ Enriched: {company_name} -> {contact_data.get('contact_name')}")
    except Exception as e:
        logger.error(f"Failed to update lead {lead_id}: {e}")

def run_enrichment():
    """Fetches leads with missing contact info and enriches them."""
    try:
        # Get leads with no contact_name
        res = supabase.table("uae_leads").select("id, company").is_("contact_name", "null").limit(20).execute()
        if not res.data:
            logger.info("No leads require enrichment at this time.")
            return
        
        for lead in res.data:
            enrich_lead(lead['id'], lead['company'])
            time.sleep(2) # Stability pause
    except Exception as e:
        logger.error(f"Enrichment Loop Error: {e}")

if __name__ == "__main__":
    run_enrichment()
