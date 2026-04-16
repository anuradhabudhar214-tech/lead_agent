import os, requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

if not SUPABASE_URL:
    # Try fetching live from the Vercel API instead
    r = requests.get("https://lead-agent-sigma.vercel.app/api/updates")
    data = r.json()
    print(f"Total leads: {len(data)}")
    for item in data[:5]:
        print(f"  Company: {item.get('company')} | contact_email: {item.get('contact_email')} | contact_name: {item.get('contact_name')}")
else:
    from supabase import create_client
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    res = sb.table("uae_leads").select("id,company,contact_email,contact_name,contact_role").limit(5).execute()
    for r in res.data:
        print(r)
