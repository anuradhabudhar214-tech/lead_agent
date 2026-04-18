import os
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# List of garbage patterns to purge from Company column
GARBAGE_PATTERNS = [
    "%Crunchbase%",
    "%LinkedIn%",
    "% - Funding%",
    "%| Profile%",
    "%Apollo.io%"
]

def cleanup():
    print("🧹 Starting Database Cleanup of garbage company names...")
    for pattern in GARBAGE_PATTERNS:
        try:
            res = supabase.table("uae_leads").delete().ilike("company", pattern).execute()
            print(f"✅ Purged pattern '{pattern}': Removed entries.")
        except Exception as e:
            print(f"❌ Error purging {pattern}: {e}")
    print("✨ Cleanup complete!")

if __name__ == "__main__":
    cleanup()
