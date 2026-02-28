import os
import json
from apify_client import ApifyClient
from dotenv import load_dotenv

load_dotenv()
api_token = os.getenv("APIFY_API_TOKEN")
client = ApifyClient(api_token)

search_actor = "harvestapi/linkedin-profile-search"
run_input = {
    "searchQuery": "Software Engineer Pakistan",
    "maxItems": 50,
    "proxyConfiguration": { "useApifyProxy": True }
}

print("Running deep debug search (50 items)...")
run = client.actor(search_actor).call(run_input=run_input)
print("Fetching results...")

items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
otw_count = sum(1 for item in items if item.get("openToWork") is True)
print(f"Total items: {len(items)}")
print(f"OTW candidates found: {otw_count}")

if items:
    with open("debug_harvest_item.json", "w", encoding="utf-8") as f:
        json.dump(items[:10], f, indent=2)
