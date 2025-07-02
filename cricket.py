import requests
from datetime import datetime, timedelta
import http.client
import json

API_TOKEN = 'EowWj4NnMhCihlx2acWj13J4AXSYpJJtPXjCcMM9BprYsttIl1PlcMHPAVcg'
BASE_URL = 'https://cricket.sportmonks.com/api/v2.0/fixtures'

# def get_matches():
    # today = datetime.utcnow().date()
    # tomorrow = today + timedelta(days=1)
    # future = today + timedelta(days=7)

    # headers = {
    #     'Accept': 'application/json'
    # }

#     # Get today's matches
#     today_url = f"{BASE_URL}?filter[starts_between]={today},{today}&api_token={API_TOKEN}&include=localteam,visitorteam"
#     today_response = requests.get(today_url, headers=headers)
#     today_matches = today_response.json().get('data', [])

#     # Get upcoming matches (from tomorrow to 7 days later)
#     upcoming_url = f"{BASE_URL}?filter[starts_between]={tomorrow},{future}&api_token={API_TOKEN}&include=localteam,visitorteam"
#     upcoming_response = requests.get(upcoming_url, headers=headers)
#     upcoming_matches = upcoming_response.json().get('data', [])

#     return {
#         'today_matches': today_matches,
#         'upcoming_matches': upcoming_matches
#     }

# # Example usage:
# if __name__ == "__main__":
#     matches = get_matches()
#     print("Today's Matches:", matches['today_matches'])
#     print("Upcoming Matches:", matches['upcoming_matches'])

# =============================================
import http.client
import json

API_TOKEN = "EowWj4NnMhCihlx2acWj13J4AXSYpJJtPXjCcMM9BprYsttIl1PlcMHPAVcg"

def fetch_json_from_api(endpoint):
    conn = http.client.HTTPSConnection("cricket.sportmonks.com")
    conn.request("GET", endpoint)
    res = conn.getresponse()
    data = res.read()
    conn.close()

    if res.status != 200:
        print(f"❌ HTTP Error {res.status}")
        return None

    try:
        return json.loads(data.decode("utf-8"))
    except json.JSONDecodeError:
        print("❌ Failed to parse JSON")
        return None

def get_team_info(team_id):
    endpoint = f"/api/v2.0/teams/{team_id}?api_token={API_TOKEN}"
    response = fetch_json_from_api(endpoint)
    if not response or "data" not in response:
        return None

    team = response["data"]
    return {
        "id": team.get("id"),
        "name": team.get("name"),
        "code": team.get("code"),
        "image_path": team.get("image_path"),
        "country_id": team.get("country_id"),
        "national_team": team.get("national_team")
    }

def get_venue_info(venue_id):
    endpoint = f"/api/v2.0/venues/{venue_id}?api_token={API_TOKEN}"
    response = fetch_json_from_api(endpoint)
    if not response or "data" not in response:
        return None

    venue = response["data"]
    return {
        "name": venue.get("name"),
        "city": venue.get("city")
    }

def get_fixture_info(fixture_id):
    endpoint = f"/api/v2.0/fixtures/{fixture_id}?api_token={API_TOKEN}"
    response = fetch_json_from_api(endpoint)
    if not response or "data" not in response:
        return None

    fixture = response["data"]
    return {
        "id": fixture.get("id"),
        "league_id": fixture.get("league_id"),
        "season_id": fixture.get("season_id"),
        "stage_id": fixture.get("stage_id"),
        "round": fixture.get("round"),
        "localteam_id": fixture.get("localteam_id"),
        "visitorteam_id": fixture.get("visitorteam_id"),
        "starting_at": fixture.get("starting_at"),
        "type": fixture.get("type"),
        "venue_id": fixture.get("venue_id")
    }

def get_last_5_matches(local_id, visitor_id):
    endpoint = f"/api/v2.0/fixtures?api_token={API_TOKEN}&include=localteam,visitorteam"
    response = fetch_json_from_api(endpoint)
    if not response or "data" not in response:
        return []

    all_fixtures = response["data"]
    head_to_head = []
    localteam_recent = []

    for fixture in all_fixtures:
        l_id = fixture.get("localteam_id")
        v_id = fixture.get("visitorteam_id")
        match = {
            "match_id": fixture.get("id"),
            "starting_at": fixture.get("starting_at"),
            "note": fixture.get("note"),
            "total_overs_played": fixture.get("total_overs_played")
        }

        # Head-to-head match
        if {l_id, v_id} == {local_id, visitor_id}:
            head_to_head.append(match)

        # Local team played (either home or away)
        if local_id in (l_id, v_id):
            localteam_recent.append(match)

    # Sort both lists by date (most recent first)
    head_to_head.sort(key=lambda x: x["starting_at"], reverse=True)
    localteam_recent.sort(key=lambda x: x["starting_at"], reverse=True)

    if head_to_head:
        return head_to_head[:5]
    else:
        return localteam_recent[:5]


# --- Main Logic ---
fixture = get_fixture_info(66233)
if fixture:
    print("✅ Fixture Info:")
    print(fixture)

    local_team = get_team_info(fixture["localteam_id"])
    visitor_team = get_team_info(fixture["visitorteam_id"])
    venue = get_venue_info(fixture["venue_id"])

    if local_team:
        print("\n🏏 Team A (Local Team):")
        print(local_team)

    if visitor_team:
        print("\n🏏 Team B (Visitor Team):")
        print(visitor_team)

    if venue:
        print("\n📍 Venue Info:")
        print(venue)

    last_matches = get_last_5_matches(fixture["localteam_id"], fixture["visitorteam_id"])
    print("\n📜 Last 5 Head-to-Head Matches:")
    for match in last_matches:
        print(match)
