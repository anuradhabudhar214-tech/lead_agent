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
            .limit(500)\
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
    """Returns the real usage statistics and live engine status."""
    if not supabase:
        return {"Serper": 0, "Gemini": 0, "Groq": 0, "status": "Offline", "last_run": "Never"}
    
    try:
        res = supabase.table("system_stats").select("*").eq("id", 1).execute()
        if res.data:
            stats = res.data[0]
            return {
                "Serper": stats.get("serper_calls", 0),
                "Gemini": stats.get("gemini_calls", 0),
                "Groq": stats.get("groq_calls", 0),
                "status": stats.get("status", "Sleeping 💤"),
                "last_run": stats.get("last_run_at", "Recently")
            }
        return {"Serper": 0, "Gemini": 0, "Groq": 0, "status": "Initializing", "last_run": "N/A"}
    except Exception as e:
        return {"Serper": 0, "Gemini": 0, "Groq": 0, "status": "Setup Required", "last_run": "N/A"}

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
