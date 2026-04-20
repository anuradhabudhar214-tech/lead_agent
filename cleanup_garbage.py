import os
from supabase import create_client, Client
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("Missing Supabase credentials.")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# List of garbage patterns to purge (Organizations, Chambers, Parks, Big Tech)
GARBAGE_PATTERNS = [
    "%Chamber%", "%Government%", "%Authority%", "%Ministry%", "%Department%",
    "%Park%", "%Centre%", "%Center%", "%Council%", "%Investopia%",
    "%University%", "%College%", "%School%", "%Summit%", "%Conference%",
    "%OpenAI%", "%Google%", "%Meta%", "%Microsoft%", "%Amazon%", "%Apple%",
    "% - Funding%", "%| Profile%", "%Apollo.io%", "%Crunchbase%", "%LinkedIn%"
]

def cleanup():
    logger.info("🧹 Starting Deep Quality Scrub of legacy leads...")
    total_purged = 0
    for pattern in GARBAGE_PATTERNS:
        try:
            res = supabase.table("uae_leads").delete().ilike("company", pattern).execute()
            if hasattr(res, 'data') and res.data:
                logger.info(f"✅ Purged pattern '{pattern}': Removed {len(res.data)} entries.")
                total_purged += len(res.data)
            else:
                logger.info(f"∅ Pattern '{pattern}': No matches.")
        except Exception as e:
            logger.error(f"❌ Error purging {pattern}: {e}")
    
    logger.info(f"✨ Deep Scrub Complete! Total Purged: {total_purged}")

if __name__ == "__main__":
    cleanup()
