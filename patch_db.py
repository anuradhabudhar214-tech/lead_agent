import os
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_patch():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    
    if not url or not key:
        logger.error("Missing Supabase credentials.")
        return

    # We use the REST API to try and add the column via a 'fake' RPC call or DDL
    # Note: This usually requires the 'service_role' key.
    
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }
    
    # Try 1: Check if the column already exists
    try:
        check_url = f"{url}/rest/v1/system_stats"
        res = requests.get(check_url, headers=headers, params={"id": "eq.1", "select": "today_scans"})
        if res.status_code == 200:
            logger.info("✅ today_scans column already exists.")
            return
    except:
        pass

    logger.warning("🚀 Missing today_scans. This normally requires Manual SQL or Service Role API.")
    logger.info("SQL TO RUN IN SUPABASE DASHBOARD:")
    logger.info("ALTER TABLE system_stats ADD COLUMN today_scans INTEGER DEFAULT 0;")

if __name__ == "__main__":
    run_patch()
