from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import json
import os
import subprocess
from datetime import datetime
from pyngrok import ngrok, conf

app = FastAPI()

STATE_FILE = "agent_state.json"
UPDATES_FILE = "found_updates.json"
URL_FILE = "dashboard_url.json"
AGENT_SCRIPT = "crunchbase_tracker.py"
AGENT_PROCESS = None

def start_ngrok():
    """Starts ngrok tunnel and saves the URL."""
    try:
        # Set authtoken explicitly
        ngrok.set_auth_token("3CLM3mw9Bkd1zvduGUXRVGCfE4G_6YnWgV1iedoo4Q4ZuhE4u")
        # Check if already running
        tunnels = ngrok.get_tunnels()
        if tunnels:
            url = tunnels[0].public_url
        else:
            # Start a new tunnel on port 5001
            # Note: Authtoken should already be configured via CLI or conf.get_default().auth_token
            public_tunnel = ngrok.connect(5001)
            url = public_tunnel.public_url
        
        with open(URL_FILE, "w") as f:
            json.dump({"url": url}, f)
        print(f"Public Dashboard URL: {url}")
        return url
    except Exception as e:
        print(f"Ngrok Error: {str(e)}")
        return None

@app.get("/api/state")
async def get_state():
    state = {"status": "Stopped", "current_task": "Idle", "last_update": "Never"}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
        except: pass
    return state

@app.get("/api/updates")
async def get_updates():
    updates = []
    if os.path.exists(UPDATES_FILE):
        try:
            with open(UPDATES_FILE, "r") as f:
                updates = json.load(f)
        except: pass
    return updates

@app.post("/api/verify")
async def verify_lead(request: Request):
    """Promotes a lead to BOTH CSVs and marks as gold."""
    data = await request.json()
    company_name = data.get("company")
    
    if os.path.exists(UPDATES_FILE):
        with open(UPDATES_FILE, "r") as f:
            updates = json.load(f)
        
        target = next((u for u in updates if u["company"] == company_name), None)
        if target:
            target["confidence_score"] = 100
            target["status"] = "Active"
            target["registry_status"] = "MANUALLY AUDITED"
            
            # Sync to BOTH CSVs
            from crunchbase_tracker import save_to_csv, CSV_MASTER, CSV_VERIFIED
            save_to_csv([target], CSV_MASTER)
            save_to_csv([target], CSV_VERIFIED)
            
            with open(UPDATES_FILE, "w") as f:
                json.dump(updates, f, indent=2)
            
            return {"status": "Verified"}
    return {"status": "Error", "message": "Lead not found"}

@app.post("/api/discard")
async def discard_lead(request: Request):
    """Removes a lead from the dashboard."""
    data = await request.json()
    company_name = data.get("company")
    
    if os.path.exists(UPDATES_FILE):
        with open(UPDATES_FILE, "r") as f:
            updates = json.load(f)
        
        new_updates = [u for u in updates if u["company"] != company_name]
        with open(UPDATES_FILE, "w") as f:
            json.dump(new_updates, f, indent=2)
            
        return {"status": "Discarded"}
    return {"status": "Error"}

@app.get("/api/usage")
async def get_usage():
    usage = {"Serper": 0, "Groq": 0}
    if os.path.exists("usage.json"):
        try:
            with open("usage.json", "r") as f:
                usage = json.load(f)
        except: pass
    return usage

@app.post("/api/start")
async def start_agent():
    global AGENT_PROCESS
    if AGENT_PROCESS is None or AGENT_PROCESS.poll() is not None:
        agent_env = os.environ.copy()
        agent_env["PYTHONIOENCODING"] = "utf-8"
        # Run the senior tracker
        AGENT_PROCESS = subprocess.Popen(["python", AGENT_SCRIPT], env=agent_env)
        return {"message": "Agent Started"}
    return {"message": "Agent already running"}

@app.post("/api/stop")
async def stop_agent():
    global AGENT_PROCESS
    if AGENT_PROCESS and AGENT_PROCESS.poll() is None:
        AGENT_PROCESS.terminate()
        AGENT_PROCESS = None
        
        state = {"status": "Stopped", "current_task": "Manually Stopped", "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
            
        return {"message": "Agent Stopped"}
    return {"message": "Agent not running"}

@app.get("/api/download/master")
async def download_master():
    """Downloads the full 70-100% database."""
    if os.path.exists("enterprise_leads_MASTER.csv"):
        from fastapi.responses import FileResponse
        return FileResponse("enterprise_leads_MASTER.csv", media_type='text/csv', filename="UAE_LEADS_ALL_70_100.csv")
    return {"error": "File missing"}

@app.get("/api/download/verified")
async def download_verified():
    """Downloads ONLY the 85%+ premium leads."""
    if os.path.exists("enterprise_leads_VERIFIED.csv"):
        from fastapi.responses import FileResponse
        return FileResponse("enterprise_leads_VERIFIED.csv", media_type='text/csv', filename="UAE_LEADS_VERIFIED_ONLY.csv")
    return {"error": "File missing"}

@app.get("/", response_class=HTMLResponse)
async def read_root():
    if os.path.exists("static/index.html"):
        with open("static/index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Dashboard UI Missing</h1>"

if __name__ == "__main__":
    import uvicorn
    # Start the tunnel before the server
    start_ngrok()
    
    if not os.path.exists("static"):
        os.makedirs("static")
    uvicorn.run(app, host="0.0.0.0", port=5001)
