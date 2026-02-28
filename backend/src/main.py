import argparse
import json
import os
from dotenv import load_dotenv
from typing import List

# Load env vars from .env file
from pathlib import Path
_backend_dir = Path(__file__).resolve().parent.parent
dotenv_path = _backend_dir / '.env'
if dotenv_path.exists():
    load_dotenv(dotenv_path=str(dotenv_path), override=True)
else:
    load_dotenv()

if not os.getenv("CEREBRAS_API_KEY"):
    print("⚠️  WARNING: CEREBRAS_API_KEY not found in environment!")

from .models import CandidateProfile
from .sourcing import SourcingEngine
from .agent import HiringAgent
from .google_sheets import GoogleSheetsExporter

def write_status(stage: str, message: str):
    """Write pipeline status to a JSON file for frontend polling."""
    import datetime
    from datetime import timezone
    status = {"stage": stage, "message": message, "timestamp": datetime.datetime.now(timezone.utc).isoformat()}
    with open("pipeline_status.json", "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2)


def stage_source(args):
    """STAGE 1: Source candidates from LinkedIn (Now with Full Profiles!)."""
    # Safety: Clear ALL old pipeline data immediately to prevent data leakage
    files_to_clear = [
        "sourced_candidates.json", 
        "ranked_candidates.json", 
        "deep_scraped_candidates.json", 
        "results.json"
    ]
    for f_path in files_to_clear:
        if os.path.exists(f_path):
            try:
                os.remove(f_path)
                with open(f_path, "w", encoding="utf-8") as f:
                    json.dump([], f)
            except Exception as e:
                print(f"⚠️ Warning: Could not clear {f_path}: {e}")

    sourcer = SourcingEngine()

    try:
        write_status("sourcing", f"Searching for '{args.role}'...")
        print(f"SEARCH: Searching for '{args.role}' in '{args.location}'...")
        candidates = sourcer.search_candidates(role=args.role, location=args.location, limit=args.search_depth)
        
        sourced_data = [c.model_dump() for c in candidates]
        with open("sourced_candidates.json", "w", encoding="utf-8") as f:
            json.dump(sourced_data, f, indent=2)
        
        # Optimization: Since we already have full profiles, we can "pre-fill" the deep scrape stage
        with open("deep_scraped_candidates.json", "w", encoding="utf-8") as f:
            json.dump(sourced_data, f, indent=2)

        print(f"DONE: Found {len(candidates)} candidates.")
        write_status("sourcing_done", f"Sourcing complete. {len(candidates)} full profiles found. No deep-scrape needed!")

        # Export sourced candidates to Google Sheets (scores will be empty until analysis)
        try:
            exporter = GoogleSheetsExporter()
            exporter.export_results(
                sourced_candidates=sourced_data,
                analysis_results=None,
                role=args.role,
            )
        except Exception as e:
            print(f"⚠️ Google Sheets export (sourcing) skipped: {e}")

    except Exception as e:
        error_msg = str(e)
        print(f"ERROR: Sourcing Failed: {error_msg}")
        write_status("error", f"Sourcing Failed: {error_msg}")


def stage_analyze(args):
    """STAGE 2: Final AI assessment on sourced candidates."""
    # Safety: Clear own results
    if os.path.exists("results.json"):
        try:
            os.remove("results.json")
            with open("results.json", "w", encoding="utf-8") as f: json.dump([], f)
        except: pass

    if not os.path.exists("sourced_candidates.json"):
        write_status("error", "No sourced candidates. Run Sourcing first.")
        print("❌ sourced_candidates.json not found. Run sourcing first.")
        return

    with open("sourced_candidates.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    candidates = [CandidateProfile(**c) for c in data]
    print(f"🧠 STAGE 2: Final AI assessment on {len(candidates)} candidates...")

    persona_text = None
    if args.persona and os.path.exists(args.persona):
        with open(args.persona, "r", encoding='utf-8') as f:
            persona_text = f.read()

    agent = HiringAgent()
    write_status("analyzing", f"AI analyzing {len(candidates)} candidates...")

    results = []
    for i, candidate in enumerate(candidates):
        write_status("analyzing", f"Assessing {i+1}/{len(candidates)}: {candidate.name}...")
        print(f"   👉 Assessing: {candidate.name}...")
        assessment = agent.assess_candidate(candidate, role_description=args.role, ideal_persona=persona_text)
        results.append(assessment.model_dump())

    with open("results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # Export to Google Sheets with scores
    try:
        exporter = GoogleSheetsExporter()
        exporter.export_results(
            sourced_candidates=data,
            analysis_results=results,
            role=args.role,
        )
    except Exception as e:
        print(f"⚠️ Google Sheets export (analysis) skipped: {e}")

    print(f"✨ DONE! {len(results)} candidates analyzed. Saved to results.json")
    write_status("done", f"Analysis complete! {len(results)} candidates assessed.")


def main():
    parser = argparse.ArgumentParser(description="AI Hiring Intelligence Agent")
    parser.add_argument("--stage", type=str, required=True, choices=["source", "analyze"], help="Pipeline stage to run")
    parser.add_argument("--role", type=str, required=True, help="Target job role")
    parser.add_argument("--location", type=str, default="Pakistan", help="Target location")
    parser.add_argument("--search_depth", type=int, default=50, help="Initial candidates to find via search")
    parser.add_argument("--persona", type=str, help="Path to Ideal Candidate Persona text file")
    parser.add_argument("--url", type=str, help="Individual URL to deep scrape")

    args = parser.parse_args()

    if args.stage == "source":
        stage_source(args)
    elif args.stage == "rank":
        stage_rank(args)
    elif args.stage == "deep-scrape":
        stage_deep_scrape(args)
    elif args.stage == "analyze":
        stage_analyze(args)


if __name__ == "__main__":
    main()
