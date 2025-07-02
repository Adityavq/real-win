import requests
from datetime import datetime
from datetime import datetime, timezone
from dotenv import load_dotenv
import os
import openai
import requests
from datetime import datetime, timedelta, timezone

load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")

BASE_URL_FOOTBALL = "https://api.sportmonks.com/v3/football/fixtures"
# BASE_URL_CRICKET = "https://cricket.sportmonks.com/api/v2.0"

def fetch_today_football_fixtures():
    today = datetime.now(timezone.utc).date()
    future = today + timedelta(days=1)

    start_date_str = today.strftime('%Y-%m-%d')
    end_date_str = future.strftime('%Y-%m-%d')

    url = f"{BASE_URL_FOOTBALL}/between/{start_date_str}/{end_date_str}?api_token={API_TOKEN}&include=statistics"
    print(f"Fetching: {url}")
    
    res = requests.get(url)
    data = res.json()

    all_matches = data.get("data", [])
    print(f"Total matches found between {start_date_str} and {end_date_str}: {len(all_matches)}")

    unplayed_matches = [match for match in all_matches if match.get("state_id") in [1, 2, 3]]

    # Optional split: today's and later
    today_str = today.strftime('%Y-%m-%d')
    today_matches = [m for m in unplayed_matches if m.get("starting_at", "").startswith(today_str)]
    upcoming_matches = [m for m in unplayed_matches if not m.get("starting_at", "").startswith(today_str)]

    return {
        "today_matches": today_matches,
        "upcoming_matches": upcoming_matches
    }

def get_team_logo(team_name):
    logo_map = {
        'Arsenal FC': '/static/images/arsenal_FC.svg',
        'Chelsea FC': '/static/images/chelsea_FC.svg',
    }
    return logo_map.get(team_name, '/static/images/logo.png') 

def fetch_today_matches_with_team_info():
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).date()
    today_str = today.strftime('%Y-%m-%d')
    url = f"https://api.sportmonks.com/v3/football/fixtures/date/{today_str}?api_token={API_TOKEN}"
    res = requests.get(url)
    data = res.json()
    all_matches = data.get("data", [])
    match_list = []
    for match in all_matches:
        match_list.append({
            "fixture_id": match.get("id"),
            "starting_at": match.get("starting_at")
        })
    return match_list



