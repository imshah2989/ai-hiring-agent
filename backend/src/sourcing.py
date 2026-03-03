import os
import re
import json
import time
from datetime import datetime, timezone
from typing import List, Optional
from apify_client import ApifyClient
from .models import CandidateProfile

# ─── SEARCH CONFIGURATION ───────────────────────────────────────────────
# Change this number to control how many profiles are scraped per search.
# For TESTING → 20
# For PRODUCTION → 100
MAX_SEARCH_PROFILES = 20
# ────────────────────────────────────────────────────────────────────────

class SourcingEngine:
    """
    Apify-powered Sourcing Funnel (Cost-Optimized Hybrid Model).
    
    DISCOVERY: Uses Google X-Ray Search (FREE) to find LinkedIn URLs.
    ENRICHMENT: Uses Dev Fusion Scraper ($10/1k) as it is more robust than Harvest.
    
    This replaces the old $100/1,000 internal LinkedIn search approach.
    """
    def __init__(self):
        self.api_token = os.getenv("APIFY_API_TOKEN")
        self.client = ApifyClient(self.api_token) if self.api_token else None
        
        # Outreach Credentials
        self.li_at = os.getenv("LINKEDIN_LI_AT")
        self.user_agent = os.getenv("LINKEDIN_USER_AGENT")
        
        # Actor IDs
        # DISCOVERY (FREE): Google Search Results Scraper
        self.google_search_actor = "apify/google-search-scraper"
        # ENRICHMENT: Dev Fusion LinkedIn Profile Scraper (Working alternative to Harvest)
        self.profile_actor = "dev_fusion/linkedin-profile-scraper"
        # Messaging: https://apify.com/addeus/send-dm-for-linkedin
        self.message_actor = "addeus/send-dm-for-linkedin"
        # Inbox: https://apify.com/randominique/linkedin-get-messages-from-unread-threads
        self.inbox_actor = "randominique/linkedin-get-messages-from-unread-threads"

    # ─── PHASE 1: DISCOVERY (Google X-Ray — FREE) ──────────────────────
    def _xray_discover(self, role: str, location: str, limit: int) -> List[str]:
        """
        Uses Google X-Ray search to find LinkedIn profile URLs.
        Query: site:linkedin.com/in/ "open to work" "role" "location"
        """
        # Balanced X-Ray query: Keep the precision of intitle: but ADD general keyword search for 'About' sections
        xray_query = f'site:linkedin.com/in/ (intitle:"open to work" OR "open to work") "{role}" "{location}"'
        
        print(f"  🔍 X-RAY DISCOVERY: Googling '{xray_query}'...")
        print(f"  🔍 Looking for up to {limit} LinkedIn URLs...")

        pages_needed = max(1, (limit + 9) // 10)

        run_input = {
            "queries": xray_query,
            "maxPagesPerQuery": pages_needed,
            "resultsPerPage": 10,
            "languageCode": "en",
            "mobileResults": False,
        }

        try:
            run = self.client.actor(self.google_search_actor).call(run_input=run_input)
            
            linkedin_urls = []
            seen = set()
            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                organic = item.get("organicResults", [])
                for result in organic:
                    url = result.get("url", "")
                    if "linkedin.com/in/" in url:
                        clean_url = url.split("?")[0]
                        if clean_url not in seen:
                            seen.add(clean_url)
                            linkedin_urls.append(clean_url)
                            if len(linkedin_urls) >= limit:
                                break
                if len(linkedin_urls) >= limit:
                    break
            
            print(f"  ✅ X-RAY DISCOVERY: Found {len(linkedin_urls)} LinkedIn URLs from Google.")
            return linkedin_urls

        except Exception as e:
            print(f"  ❌ X-RAY DISCOVERY Error: {e}")
            return []

    # ─── PHASE 2: ENRICHMENT (Dev Fusion) ─────────────────────────────
    def _enrich_profiles(self, urls: List[str]) -> List[dict]:
        """
        Uses the Dev Fusion LinkedIn Profile Scraper to get full profile data.
        """
        if not urls:
            return []
        
        print(f"  📋 ENRICHMENT: Scraping {len(urls)} profiles via Dev Fusion...")

        run_input = {
            "profileUrls": urls,
            "proxy": { "useApifyProxy": True }
        }

        try:
            run = self.client.actor(self.profile_actor).call(run_input=run_input)
            
            profiles = []
            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                profiles.append(item)
            
            print(f"  ✅ ENRICHMENT: Got {len(profiles)} full profiles.")
            return profiles

        except Exception as e:
            print(f"  ❌ ENRICHMENT Error: {e}")
            return []

    # ─── MAIN SEARCH (Hybrid: X-Ray + Enrich) ─────────────────────────
    def search_candidates(self, role: str, location: str, limit: int = 2500) -> List[CandidateProfile]:
        """
        HYBRID SEARCH (Cost-Optimized):
        1. Google X-Ray finds LinkedIn URLs          → FREE
        2. Dev Fusion scrapes full profile details    → Cost-Effective
        """
        if not self.client:
            print("⚠️ Skipping search: APIFY_API_TOKEN not set.")
            return []

        effective_limit = min(limit, MAX_SEARCH_PROFILES)
        print(f"\n{'='*60}")
        print(f"🚀 HYBRID SEARCH: '{role}' in '{location}' (max {effective_limit})")
        print(f"{'='*60}")

        # PHASE 1: Discover URLs via Google X-Ray
        urls = self._xray_discover(role, location, effective_limit)
        if not urls:
            print("⚠️ No LinkedIn URLs found via X-Ray. Try a different role/location.")
            return []

        # PHASE 2: Enrich profiles
        raw_profiles = self._enrich_profiles(urls)
        if not raw_profiles:
            print("⚠️ Enrichment returned no data.")
            return []

        # PHASE 3: Map to CandidateProfile
        candidates = []
        otw_keywords = ["open to work", "actively looking", "seeking", "available for", "looking for new"]
        
        for item in raw_profiles:
            # ROBUST MAPPING (Handles both Harvest and Dev Fusion schemas)
            name = item.get("fullName") or item.get("name") or f"{item.get('firstName', '')} {item.get('lastName', '')}".strip()
            if not name or name.lower() == "linkedin member":
                name = item.get("publicIdentifier") or "Unknown Candidate"
            
            headline = (item.get("jobTitle") or item.get("headline") or "").lower()
            about = (item.get("description") or item.get("summary") or item.get("about") or "").lower()
            
            # BROAD OTW check: check specific flag + keywords in headline and about
            is_otw = item.get("openToWork") is True or any(kw in headline for kw in otw_keywords) or any(kw in about for kw in otw_keywords)
            
            # USER REQUEST: Only return Open to Work candidates
            if not is_otw:
                print(f"  ❌ SKIPPING: {name} (Not actively 'Open to Work')")
                print(f"     Headline: {headline[:60]}...")
                # Also check for common "hired" indicators to be smart
                continue

            profile_url = item.get("linkedinUrl") or item.get("url") or item.get("profileUrl")
            loc_obj = item.get("location")
            location_text = ""
            if isinstance(loc_obj, dict):
                location_text = loc_obj.get("linkedinText") or loc_obj.get("name") or ""
            elif isinstance(loc_obj, str):
                location_text = loc_obj
            
            # FALLBACK: If location is empty, try to infer it from the URL (e.g., pk.linkedin.com -> Pakistan)
            if not location_text and profile_url:
                if "pk.linkedin.com" in profile_url: location_text = "Pakistan"
                elif "uk.linkedin.com" in profile_url: location_text = "United Kingdom"
                elif "ae.linkedin.com" in profile_url: location_text = "United Arab Emirates"
                elif "sa.linkedin.com" in profile_url: location_text = "Saudi Arabia"
                elif "in.linkedin.com" in profile_url: location_text = "India"

            # USER REQUEST: Strict Location Filter
            # Verify that the live profile location actually matches the search query
            location_match = not location or location.lower() in location_text.lower()
            if not location_match:
                print(f"  ❌ SKIPPING: {name} (Location mismatch: {location_text} vs {location})")
                continue
                
            experience = item.get("experience") or []
            
            candidates.append(CandidateProfile(
                id=profile_url or name,
                name=name,
                headline=item.get("jobTitle") or item.get("headline") or "",
                profile_url=profile_url,
                location=location_text,
                experience_text=json.dumps(experience) if experience else "",
                about=item.get("description") or item.get("summary") or item.get("about"),
                is_open_to_work=True # We already filtered
            ))

        print(f"\n{'='*60}")
        print(f"✅ HYBRID SEARCH COMPLETE")
        print(f"   Candidates filtered for Open-to-Work: {len(candidates)}")
        print(f"{'='*60}\n")
        
        return candidates

    def deep_scrape_candidates(self, candidates: List[CandidateProfile], only_open_to_work: bool = False) -> List[CandidateProfile]:
        """
        Enriches candidates using the Apify Profile Scraper.
        """
        if not self.client or not candidates:
            return candidates

        valid_urls = [c.profile_url for c in candidates if c.profile_url]
        if not valid_urls:
            return candidates

        print(f"SCRAPE: RE-Enriching {len(valid_urls)} profiles via Apify...")
        
        raw_profiles = self._enrich_profiles(valid_urls)
        
        enriched_data = {}
        for item in raw_profiles:
            url = item.get("url") or item.get("profileUrl") or item.get("linkedinUrl")
            if url:
                enriched_data[url] = item

        results = []
        for c in candidates:
            if c.profile_url in enriched_data:
                data = enriched_data[c.profile_url]
                c.headline = data.get("jobTitle") or data.get("headline") or c.headline
                c.experience_text = json.dumps(data.get("experience", []))
                c.is_open_to_work = data.get("openToWork", False) or "open to work" in (data.get("jobTitle") or data.get("headline") or "").lower()
                
                if only_open_to_work and not c.is_open_to_work:
                    continue
                    
            results.append(c)
            
        return results

    def send_outreach(self, profile_url: str, message_text: str) -> bool:
        """
        Sends a LinkedIn DM using Apify.
        """
        if not self.client:
            return False
            
        if not self.li_at:
            return False

        print(f"OUTREACH: Sending Apify Outreach to {profile_url}...")
        
        run_input = {
            "profileUrl": profile_url,
            "messageText": message_text,
            "liAtCookie": self.li_at,
            "userAgent": self.user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        }

        try:
            self.client.actor(self.message_actor).call(run_input=run_input)
            return True
        except Exception as e:
            return False

    def check_replies(self) -> List[dict]:
        """
        Checks for unread LinkedIn messages using Apify.
        """
        if not self.client:
            return []

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
            return []
