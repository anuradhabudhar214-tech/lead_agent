import os
import time
import requests
import json
import logging
from supabase import create_client, Client

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
APOLLO_API_KEYS_STR = os.environ.get("APOLLO_API_KEYS", "yD4WPjUpffUdIlSq-Y52xw,_3nLDK3dz0dAJxW6xkXIiQ,bzdlDsyOn1EpXSZGAo767g")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("Supabase credentials missing.")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
apollo_keys = [k.strip() for k in APOLLO_API_KEYS_STR.split(",") if k.strip()]

class ApolloVault:
    def __init__(self, keys):
        self.keys = keys
        self.current_idx = 0
        
    def get_key(self):
        if not self.keys: return None
        return self.keys[self.current_idx]
        
    def rotate(self):
        self.current_idx += 1
        if self.current_idx >= len(self.keys):
            logger.error("🚨 All Apollo keys exhausted!")
            return False
        logger.warning(f"🔄 Rotated to Apollo Key #{self.current_idx + 1}")
        return True

vault = ApolloVault(apollo_keys)

def search_apollo_person(company_name):
    titles = ["ceo", "founder", "cto", "managing director", "chief executive"]
    for attempt in range(len(vault.keys)):
        api_key = vault.get_key()
        if not api_key: return None
        
        url = "https://api.apollo.io/v1/mixed_people/search"
        headers = {
            "Cache-Control": "no-cache",
            "Content-Type": "application/json"
        }
        data = {
            "api_key": api_key,
            "q_organization_name": company_name,
            "person_titles": titles,
            "page": 1,
            "per_page": 3
        }
        
        try:
            r = requests.post(url, headers=headers, json=data)
            if r.status_code == 429 or r.status_code == 401: # Limit hit or invalid
                logger.warning(f"Apollo API Limit hit on key ending in {api_key[-4:]}")
                if vault.rotate(): continue
                else: break
            
            res = r.json()
            people = res.get("people", [])
            
            # Find the best match with an email
            for p in people:
                if p.get("email"):
                    return {
                        "name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                        "email": p.get("email"),
                        "title": p.get("title")
                    }
            return None # No one found with email
        except Exception as e:
            logger.error(f"Error querying Apollo: {e}")
            break
            
    return None

def run_enrichment():
    logger.info("Starting Apollo Enrichment Cycle...")
    
    # 1. Fetch leads missing contact info
    res = supabase.table("uae_leads").select("*").is_("contact_email", "null").eq("status", "Pending").limit(10).execute()
    leads = res.data
    
    if not leads:
        logger.info("No new leads require enrichment at this time.")
        return
        
    logger.info(f"🔍 Found {len(leads)} leads requiring enrichment. Connecting to Apollo...")
    
    for lead in leads:
        company = lead.get("company")
        lead_id = lead.get("id")
        logger.info(f"Hunting contacts for: {company}")
        
        contact = search_apollo_person(company)
        
        if contact:
            logger.info(f"✅ Found! {contact['name']} - {contact['title']} | {contact['email']}")
            # Update Supabase
            supabase.table("uae_leads").update({
                "contact_name": contact["name"],
                "contact_email": contact["email"],
                "contact_role": contact["title"]
            }).eq("id", lead_id).execute()
        else:
            logger.info(f"❌ No verifiable contact found with email for {company}.")
            # Mark as not found to avoid infinite retrying using a placeholder
            supabase.table("uae_leads").update({
                "contact_email": "Not Found"
            }).eq("id", lead_id).execute()
            
        time.sleep(2) # Safe API pacing

if __name__ == "__main__":
    run_enrichment()
    logger.info("Enrichment Cycle Complete.")
