import os
import sys
import subprocess
import json
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from src.sourcing import SourcingEngine
from src.notifications import NotificationManager
from src.agent import HiringAgent

# Load .env from the backend directory
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)

if not os.getenv("CEREBRAS_API_KEY"):
    print("⚠️  WARNING: CEREBRAS_API_KEY not found — AI analysis will fail!")
if not os.getenv("APIFY_API_TOKEN"):
    print("⚠️  WARNING: APIFY_API_TOKEN not found — Sourcing & Outreach will fail!")
else:
    print("✅ CEREBRAS_API_KEY & APIFY_API_TOKEN loaded successfully.")

app = FastAPI(title="AI Hiring Agent API")

@app.get("/")
def root():
    return {"status": "online", "message": "AI Hiring Agent API is operational", "docs": "/docs"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class SourcingRequest(BaseModel):
    role: str
    location: str = "United States"
    search_depth: int = 10

class AnalyzeRequest(BaseModel):
    role: str
    persona: str

class OutreachRequest(BaseModel):
    candidate_id: str
    personalized_message: str

sourcing_engine = SourcingEngine()
notification_manager = NotificationManager()
agent = HiringAgent()

@app.on_event("startup")
async def startup_event():
    print("\n" + "="*50)
    print("🚀 TALENT SCOUT BACKEND STARTING")
    
    # Start background polling for LinkedIn replies
    import threading
    import time
    
    def poll_replies_worker():
        print("🕒 Background Polling Started: Checking for replies every 10 mins...")
        seen_replies_path = Path("seen_replies.json")
        
        while True:
            try:
                # 1. Load seen IDs
                seen_ids = set()
                if seen_replies_path.exists():
                    with open(seen_replies_path, "r") as f:
                        seen_ids = set(json.load(f))
                
                # 2. Check for replies
                print("🔍 Background check for new LinkedIn replies...")
                threads = sourcing_engine.check_replies()
                new_ids = []
                
                for thread in threads:
                    # Apify Unread Messages Scraper keys
                    thread_url = thread.get('threadUrl') or thread.get('profileUrl')
                    snippet = thread.get('text') or 'No text'
                    sender = thread.get('from') or 'A candidate'
                    msg_id = thread.get('id') or f"{thread_url}_{sender}"
                    
                    if msg_id not in seen_ids:
                        print(f"🚨 New reply from {sender}! Sending WhatsApp notification...")
                        notification_manager.notify_new_reply(sender, snippet)
                        seen_ids.add(msg_id)
                        new_ids.append(msg_id)
                
                # 3. Save seen IDs
                if new_ids:
                    with open(seen_replies_path, "w") as f:
                        json.dump(list(seen_ids), f)
                        
            except Exception as e:
                print(f"⚠️ Polling Error: {e}")
            
            # Wait 4 hours (14400 seconds) — was 10 min, changed to save Apify credits
            time.sleep(14400)

    polling_thread = threading.Thread(target=poll_replies_worker, daemon=True)
    polling_thread.start()

    if os.getenv("CEREBRAS_API_KEY"):
        print("✅ CEREBRAS API KEY: LOADED")
    else:
        print("❌ CEREBRAS API KEY: MISSING")
    print("="*50 + "\n")

def write_status(stage: str, message: str):
    """Write pipeline status to a JSON file for frontend polling."""
    import datetime
    from datetime import timezone
    status = {"stage": stage, "message": message, "timestamp": datetime.datetime.now(timezone.utc).isoformat()}
    try:
        with open("pipeline_status.json", "w", encoding="utf-8") as f:
            json.dump(status, f, indent=2)
    except Exception as e:
        print(f"⚠️ Warning: Could not write status: {e}")

from src.main import stage_source, stage_analyze

def _run_stage(stage: str, role: str, location: str = "United States", search_depth: int = 10, persona_text: str = None):
    """Run a specific pipeline stage in a background thread."""
    # Save persona if provided
    if persona_text:
        with open("persona.txt", "w", encoding="utf-8") as f:
            f.write(persona_text)

    # IMMEDIATE STATUS RESET & FILE CLEARING
    status_map = {
        "source": ("sourcing", f"Initializing search for '{role}'..."),
        "analyze": ("analyzing", "Initializing Analysis...")
    }
    s_stage, s_msg = status_map.get(stage, (stage, f"Starting {stage}..."))
    
    # IMMEDIATE FILE CLEARING: Prevent frontend from seeing stale results
    files_to_zero = ["results.json", "pipeline_status.json"]
    if stage == "source":
        files_to_zero.append("sourced_candidates.json")
        files_to_zero.append("analysis.log") # Clear logs for fresh start
    
    import datetime
    from datetime import timezone
    
    for f in files_to_zero:
        try:
            with open(f, "w", encoding="utf-8") as f_out:
                if f == "pipeline_status.json":
                    json.dump({
                        "stage": s_stage, 
                        "message": s_msg, 
                        "timestamp": datetime.datetime.now(timezone.utc).isoformat()
                    }, f_out)
                else:
                    json.dump([], f_out)
        except: pass

    # Mock Args object for main.py stage functions
    class MockArgs:
        def __init__(self, **kwargs):
            for k, v in kwargs.items(): setattr(self, k, v)

    def worker():
        try:
            import datetime
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            log_msg = f"\n\n--- [{timestamp}] Threaded Stage: {stage} for {role} ---\n"
            with open("analysis.log", "a", encoding="utf-8") as log_file:
                log_file.write(log_msg)
            
            # Simple wrapper to capture print statements to analysis.log
            import sys
            class LoggerWrapper:
                def __init__(self, original_stdout, log_file_path):
                    self.original_stdout = original_stdout
                    self.log_file_path = log_file_path
                def write(self, message):
                    self.original_stdout.write(message)
                    with open(self.log_file_path, "a", encoding="utf-8") as f:
                        f.write(message)
                def flush(self):
                    self.original_stdout.flush()

            sys.stdout = LoggerWrapper(sys.stdout, "analysis.log")
            
            args = MockArgs(
                stage=stage, 
                role=role, 
                location=location, 
                search_depth=search_depth, 
                persona="persona.txt" if persona_text else None
            )
            
            if stage == "source":
                stage_source(args)
            elif stage == "analyze":
                stage_analyze(args)
            
            # Restore stdout
            sys.stdout = sys.stdout.original_stdout
        except Exception as e:
            with open("analysis.log", "a", encoding="utf-8") as f:
                f.write(f"CRITICAL THREAD ERROR: {e}\n")
            write_status("error", f"Backend Error: {e}")

    threading.Thread(target=worker, daemon=True).start()


# ─── STAGE 1: SOURCE ────────────────────────────────────────────────
@app.post("/start-sourcing")
def start_sourcing(req: SourcingRequest):
    try:
        _run_stage("source", req.role, req.location, req.search_depth)
        return {"status": "started", "message": "Sourcing started. Searching LinkedIn for Open-to-Work candidates..."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── STAGE 2: AI ANALYZE (Final AI assessment) ──────────────────────
@app.post("/start-analyze")
def start_analyze(req: AnalyzeRequest):
    if not os.path.exists("sourced_candidates.json"):
        raise HTTPException(status_code=400, detail="No sourced candidates. Run Sourcing first.")
    try:
        _run_stage("analyze", req.role, persona_text=req.persona)
        return {"status": "started", "message": "Running AI assessment on sourced profiles..."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── DATA ENDPOINTS ─────────────────────────────────────────────────
@app.get("/sourced")
def get_sourced():
    if not os.path.exists("sourced_candidates.json"):
        return {"sourced": []}
    with open("sourced_candidates.json", "r", encoding="utf-8") as f:
        return {"sourced": json.load(f)}

@app.get("/results")
def get_results():
    if not os.path.exists("results.json"):
        return {"results": []}
    with open("results.json", "r", encoding="utf-8") as f:
        return {"results": json.load(f)}

@app.get("/status")
def get_status(response: Response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    if not os.path.exists("pipeline_status.json"):
        return {"stage": "idle", "message": "No analysis running."}
    with open("pipeline_status.json", "r", encoding="utf-8") as f:
        return json.load(f)

@app.get("/logs")
def get_logs():
    """Returns the last 100 lines of analysis.log for debugging."""
    if not os.path.exists("analysis.log"):
        return {"logs": "No logs found."}
    try:
        with open("analysis.log", "r", encoding="utf-8") as f:
            lines = f.readlines()
            return {"logs": "".join(lines[-100:])}
    except Exception as e:
        return {"logs": f"Error reading logs: {e}"}

@app.post("/send-outreach")
def send_outreach(req: OutreachRequest):
    """Trigger the LinkedIn Message Sender Phantom."""
    try:
        success = sourcing_engine.send_outreach(req.candidate_id, req.personalized_message)
        if success:
            return {"status": "success", "message": f"Message sent to {req.candidate_id}"}
        else:
            raise HTTPException(status_code=500, detail="Failed to launch Phantom")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/generate-message")
def generate_message(candidate_id: str, role: str):
    """Use AI to generate a personalized message based on the assessment."""
    try:
        results_path = Path("results.json")
        candidate = None
        if results_path.exists():
            with open(results_path, "r", encoding="utf-8") as f:
                results = json.load(f)
            candidate = next((c for c in results if c.get('candidate_id') == candidate_id), None)
        if not candidate:
            ds_path = Path("deep_scraped_candidates.json")
            if ds_path.exists():
                with open(ds_path, "r", encoding="utf-8") as f:
                    ds = json.load(f)
                    candidate = next((c for c in ds if c.get('id') == candidate_id), None)
        if not candidate:
            return {"message": f"Hi, I saw your profile for the {role} role and would love to chat!"}
        strengths = candidate.get('role_fit_analysis', {}).get('strengths', [])
        strength = strengths[0] if strengths else "impressive background"
        prompt = f"Write a professional, warm 2-sentence LinkedIn outreach message for a {role} role. Mention their specific strength: {strength}. Keep it under 300 characters."
        resp = agent.client.chat.completions.create(model=agent.model, messages=[{"role": "user", "content": prompt}])
        return {"message": resp.choices[0].message.content.strip()}
    except Exception as e:
        return {"message": f"Hi, I saw your profile for the {role} role and would love to chat!"}

@app.get("/check-replies")
@app.post("/check-replies")
def check_replies():
    """Manual trigger to check for LinkedIn replies and send WhatsApp alerts."""
    try:
        threads = sourcing_engine.check_replies()
        new_replies_count = 0
        for thread in threads:
            last_msg = thread.get('lastMessage', {})
            if not last_msg.get('fromMe'):
                name = thread.get('fullName', 'A candidate')
                snippet = last_msg.get('text', 'No text')
                notification_manager.notify_new_reply(name, snippet)
                new_replies_count += 1
        return {"status": "success", "replies_found": new_replies_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
