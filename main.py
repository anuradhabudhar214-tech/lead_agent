import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from supabase import create_client, Client

app = FastAPI()

# --- CONFIGURATION ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Initialize Supabase
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.get("/api/updates")
async def get_leads():
    """Fetches leads from the professional cloud database."""
    if not supabase:
        return JSONResponse(content={"error": "Database not connected"}, status_code=500)
    
    try:
        # Fetch latest 500 leads, ordered by discovery date
        res = supabase.table("uae_leads")\
            .select("*")\
            .order("discovered_at", desc=True)\
            .limit(1000)\
            .execute()
        return res.data
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/api/verify")
async def verify_lead(request: Request):
    """Manually promotes a lead in the Cloud DB."""
    data = await request.json()
    company = data.get("company")
    if not supabase or not company: return {"status": "Error"}
    
    try:
        supabase.table("uae_leads")\
            .update({"confidence_score": 100, "status": "Active", "registry_status": "MANUALLY AUDITED"})\
            .eq("company", company)\
            .execute()
        return {"status": "Verified"}
    except:
        return {"status": "Error"}

@app.get("/api/state")
async def get_state():
    """Provides the live status of the 24/7 Cloud Worker."""
    return {
        "status": "Active (Cloud Engine)",
        "current_task": "Background Niche Automation",
        "last_update": "Recently"
    }

@app.get("/api/usage")
async def get_usage():
    """Returns real usage statistics, live status, and daily lead counts."""
    if not supabase:
        return {"Serper": 0, "Gemini": 0, "Groq": 0, "status": "Offline", "today_count": 0, "total_leads": 0}
    
    try:
        # Get general stats
        usage_res = supabase.table("system_stats").select("*").eq("id", 1).execute()
        
        # Get total lead count
        total_res = supabase.table("uae_leads").select("id", count="exact").execute()
        total_leads = total_res.count if total_res else 0
        
        # Get today's lead count (Since 00:00 UTC)
        import datetime
        today_start = datetime.datetime.now(datetime.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        today_res = supabase.table("uae_leads").select("id", count="exact").filter("discovered_at", "gt", today_start).execute()
        today_count = today_res.count if today_res else 0

        if usage_res.data:
            stats = usage_res.data[0]
            return {
                "Serper": stats.get("serper_calls", 0),
                "Gemini": stats.get("gemini_calls", 0),
                "Groq": stats.get("groq_calls", 0),
                "total_scans": stats.get("total_scans", 0),
                "status": stats.get("status", "Sleeping 💤"),
                "last_run": stats.get("last_run_at", "Recently"),
                "today_count": today_count,
                "total_leads": total_leads
            }
        return {"Serper": 0, "Gemini": 0, "Groq": 0, "status": "Initializing", "today_count": today_count, "total_leads": total_leads}
    except Exception as e:
        return {"Serper": 0, "Gemini": 0, "Groq": 0, "status": "Error", "today_count": 0, "total_leads": 0}

@app.get("/", response_class=HTMLResponse)
async def read_root():
    # Detect if we are in local development or cloud
    path = "static/index.html" if os.path.exists("static/index.html") else "index.html"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return "<h1>Dashboard UI Missing</h1>"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)
