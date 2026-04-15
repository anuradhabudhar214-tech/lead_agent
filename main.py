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

import io
import csv
from fastapi.responses import Response

@app.get("/api/download/{type}")
async def download_csv(type: str):
    """Downloads leads as a CSV file."""
    if not supabase: return JSONResponse(content={"error": "Database error"}, status_code=500)
    try:
        # Verified gives 85+ certainty, Master gives 70+
        threshold = 85 if type == "verified" else 70
        res = supabase.table("uae_leads").select("*").gte("confidence_score", threshold).order("discovered_at", desc=True).execute()
        
        output = io.StringIO()
        if res.data:
            headers = ["company", "industry", "confidence_score", "strategic_signal", "integration_opportunity", "patron_chairman", "ceo_founder", "financials", "registry_status", "status", "url", "discovered_at"]
            writer = csv.DictWriter(output, fieldnames=headers, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(res.data)
            
        csv_data = output.getvalue()
        return Response(content=csv_data, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=uae_leads_{type}.csv"})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

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
    return {"status": "Active (Cloud Engine)", "current_task": "Background Niche Automation"}

@app.post("/api/control")
async def control_agent(request: Request):
    """Manually start or stop the cloud engine."""
    data = await request.json()
    action = data.get("action")
    if not supabase: return {"status": "Error", "message": "No DB connection"}
    
    try:
        if action == "stop":
            supabase.table("system_stats").update({"status": "Paused ⏸️"}).eq("id", 1).execute()
            return {"status": "Success", "message": "Engine Paused"}
        elif action == "start":
            supabase.table("system_stats").update({"status": "Waking Up 🌅"}).eq("id", 1).execute()
            
            # Fire the GitHub Action to instantly start hunting if requests is available
            try:
                import requests
                gh_pat = os.getenv("GH_PAT")
                if gh_pat:
                    h = {
                        "Authorization": f"Bearer {gh_pat}",
                        "Accept": "application/vnd.github.v3+json"
                    }
                    requests.post(
                        "https://api.github.com/repos/anuradhabudhar214-tech/lead_agent/actions/workflows/auditor_hunt.yml/dispatches",
                        json={"ref": "main"}, headers=h, timeout=5
                    )
            except: pass
            
            return {"status": "Success", "message": "Engine Started"}
    except Exception as e:
        return {"status": "Error", "message": str(e)}

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
