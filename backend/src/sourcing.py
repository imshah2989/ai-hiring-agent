import os
import json
import time
from datetime import datetime, timezone
from typing import List, Optional
from apify_client import ApifyClient
from .models import CandidateProfile

# ─── SEARCH CONFIGURATION ───────────────────────────────────────────────
# Change this number to control how many profiles are scraped per search.
# For TESTING → 50
# For PRODUCTION → 2500 (LinkedIn's hard cap per query)
MAX_SEARCH_PROFILES = 50
# ────────────────────────────────────────────────────────────────────────

class SourcingEngine:
    """
    Apify-powered Sourcing Funnel.
    1. Search (LinkedIn People Search Scraper) -> Sourcing.
    2. Profile Scrape (LinkedIn Profile Scraper) -> Deep Scrape.
    3. Messaging (Send DM for LinkedIn) -> Outreach.
    4. Inbox (LinkedIn Unread Messages Scraper) -> Notifications.
    """
    def __init__(self):
        self.api_token = os.getenv("APIFY_API_TOKEN")
        self.client = ApifyClient(self.api_token) if self.api_token else None
        
        # Outreach Credentials
        self.li_at = os.getenv("LINKEDIN_LI_AT")
        self.user_agent = os.getenv("LINKEDIN_USER_AGENT")
        
        # Actor IDs (Using verified reliable actors)
        # Search & Profile: https://apify.com/harvestapi/linkedin-profile-search
        self.search_actor = "harvestapi/linkedin-profile-search"
        # Profile Scrape: Using the same HarvestAPI actor or specialized profile scraper
        self.profile_actor = "harvestapi/linkedin-profile-scraper"
        # Messaging: https://apify.com/addeus/send-dm-for-linkedin
        self.message_actor = "addeus/send-dm-for-linkedin"
        # Inbox: https://apify.com/randominique/linkedin-get-messages-from-unread-threads
        self.inbox_actor = "randominique/linkedin-get-messages-from-unread-threads"

    def search_candidates(self, role: str, location: str, limit: int = 2500) -> List[CandidateProfile]:
        """
        Runs the Apify Search Actor to find candidates.
        Fetches up to 2500 profiles (LinkedIn's maximum per query),
        then filters for Open-to-Work candidates from the full pool.
        """
        if not self.client:
            print("⚠️ Skipping search: APIFY_API_TOKEN not set.")
            return []

        print(f"SEARCH: Launching Apify Search for '{role}' in '{location}'...")
        print(f"SEARCH: Fetching max 2500 profiles, then filtering for Open-to-Work...")
        
        # Prepare search keywords
        query = f"{role} {location}"
        
        run_input = {
            "searchQuery": query,
            "maxItems": MAX_SEARCH_PROFILES,  # Change MAX_SEARCH_PROFILES at the top of this file
            "proxyConfiguration": { "useApifyProxy": True }
        }

        try:
            run = self.client.actor(self.search_actor).call(run_input=run_input)
            print(f"DONE: Search complete. Fetching results...")
            
            candidates = []
            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                # ROBUST NAME MAPPING: HarvestAPI uses firstName/lastName
                f_name = item.get("firstName") or ""
                l_name = item.get("lastName") or ""
                name = item.get("fullName") or item.get("name") or f"{f_name} {l_name}".strip()
                if not name or name.lower() == "linkedin member":
                    name = item.get("publicIdentifier") or "Unknown Candidate"
                
                # Check OTW status (Both boolean and headline keyword)
                headline = item.get("headline") or ""
                is_otw = item.get("openToWork") is True or "open to work" in headline.lower()
                
                # STRICT FILTER: Only process those interested in opportunities
                if not is_otw:
                    continue

                profile_url = item.get("linkedinUrl") or item.get("url") or item.get("profileUrl")
                loc_obj = item.get("location")
                location_text = ""
                if isinstance(loc_obj, dict):
                    location_text = loc_obj.get("linkedinText") or loc_obj.get("name") or ""
                
                # Capture full data
                about = item.get("about") or item.get("summary")
                experience = item.get("experience") or []
                
                candidates.append(CandidateProfile(
                    id=profile_url or name,
                    name=name,
                    headline=headline,
                    profile_url=profile_url,
                    location=location_text,
                    experience_text=json.dumps(experience) if experience else "",
                    about=about,
                    is_open_to_work=is_otw
                ))
            
            print(f"DONE: Filtered for {len(candidates)} Open-to-Work candidates.")
            return candidates

        except Exception as e:
            print(f"ERROR: Apify Search Error: {e}")
            return []

    def deep_scrape_candidates(self, candidates: List[CandidateProfile], only_open_to_work: bool = False) -> List[CandidateProfile]:
        """
        Enriches candidates using the Apify Profile Scraper.
        """
        if not self.client or not candidates:
            return candidates

        valid_urls = [c.profile_url for c in candidates if c.profile_url]
        if not valid_urls:
            return candidates

        print(f"SCRAPE: Deep Scraping {len(valid_urls)} profiles via Apify...")
        
        run_input = {
            "profileUrls": valid_urls,
            "maxItems": len(valid_urls),
            "proxyConfiguration": { "useApifyProxy": True }
        }

        try:
            run = self.client.actor(self.profile_actor).call(run_input=run_input)
            
            enriched_data = {}
            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                url = item.get("url") or item.get("profileUrl") or item.get("linkedinUrl")
                if url:
                    enriched_data[url] = item

            results = []
            for c in candidates:
                if c.profile_url in enriched_data:
                    data = enriched_data[c.profile_url]
                    
                    # Update candidate with full data
                    c.headline = data.get("headline") or c.headline
                    c.experience_text = json.dumps(data.get("experience", []))
                    # Native HarvestAPI OTW flag
                    c.is_open_to_work = data.get("openToWork", False) or "open to work" in (data.get("headline") or "").lower()
                    
                    if only_open_to_work and not c.is_open_to_work:
                        continue # Skip if we only want OTW and this one isn't
                        
                results.append(c)
                
            return results

        except Exception as e:
            print(f"❌ Apify Deep Scrape Error: {e}")
            return candidates

    def send_outreach(self, profile_url: str, message_text: str) -> bool:
        """
        Sends a LinkedIn DM using Apify.
        """
        if not self.client:
            print("⚠️ Outreach failed: APIFY_API_TOKEN not set.")
            return False
            
        if not self.li_at:
            print("⚠️ Outreach failed: LINKEDIN_LI_AT cookie not set in .env.")
            return False

        print(f"OUTREACH: Sending Apify Outreach to {profile_url}...")
        
        # Addeus actor schema: profileUrl, messageText, liAtCookie, userAgent
        run_input = {
            "profileUrl": profile_url,
            "messageText": message_text,
            "liAtCookie": self.li_at,
            "userAgent": self.user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        }

        try:
            self.client.actor(self.message_actor).call(run_input=run_input)
            print(f"DONE: Message sent successfully.")
            return True
        except Exception as e:
            print(f"❌ Apify Message Error: {e}")
            return False

    def check_replies(self) -> List[dict]:
        """
        Checks for unread LinkedIn messages using Apify.
        """
        if not self.client:
            return []

        print(f"INBOX: Checking for new replies via Apify...")
        
        try:
            run = self.client.actor(self.inbox_actor).call()
            
            replies = []
            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                replies.append({
                    "from": item.get("senderName"),
                    "text": item.get("lastMessage"),
                    "threadUrl": item.get("threadUrl")
                })
            return replies
        except Exception as e:
            print(f"❌ Apify Inbox Error: {e}")
            return []
