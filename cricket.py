import http.client
import json
import os
from config import CRICKET_API_KEY, CRICKET_PROJECT_ID
from datetime import datetime, timezone, timedelta

def token_create_or_get():
    conn = http.client.HTTPSConnection("api.sports.roanuz.com")
    payload = json.dumps({
        "api_key": CRICKET_API_KEY
    })
    headers = {
        'Content-Type': 'application/json'
    }

    conn.request("POST", f"/v5/core/{CRICKET_PROJECT_ID}/auth/", payload, headers)
    res = conn.getresponse()
    data = res.read()

    try:
        response_json = json.loads(data.decode("utf-8"))
        if response_json.get("data") and "token" in response_json["data"]:
            return response_json["data"]["token"]
        else:
            print("❌ Token fetch failed:", response_json.get("error", "Unknown error"))
            return None
    except json.JSONDecodeError:
        print("❌ Failed to decode token response.")
        return None

def convert_unix_to_ist(timestamp):
    dt_utc = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    ist = dt_utc.astimezone(timezone(timedelta(hours=5, minutes=30)))
    return ist

def get_featured_matches(date_str):
    token = token_create_or_get()
    if not token:
        print("Failed to retrieve token.")
        return []

    conn = http.client.HTTPSConnection("api.sports.roanuz.com")
    headers = {
        'rs-token': token
    }

    conn.request("GET", f"/v5/cricket/{CRICKET_PROJECT_ID}/featured-matches-2/", '', headers)
    res = conn.getresponse()
    data = res.read()
    response_json = json.loads(data.decode("utf-8"))

    # Parse the target date
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()

    filtered_matches = []
    for match in response_json.get("data", {}).get("matches", []):
        if match.get("status") == "not_started" and match.get("start_at"):
            start_ist = convert_unix_to_ist(match["start_at"])
            match_date = start_ist.date()

            if match_date == target_date:
                match["start_at_human"] = start_ist.strftime('%Y-%m-%d %H:%M:%S')
                filtered_matches.append(match)

    return filtered_matches


def get_last_five_matches(team_name):
    token = token_create_or_get()
    if not token:
        print("❌ Failed to retrieve token.")
        return []

    conn = http.client.HTTPSConnection("api.sports.roanuz.com")
    headers = {
        'rs-token': token
    }

    conn.request("GET", f"/v5/cricket/{CRICKET_PROJECT_ID}/featured-matches-2/", '', headers)
    res = conn.getresponse()
    data = res.read()
    response_json = json.loads(data.decode("utf-8"))

    all_matches = response_json.get("data", {}).get("matches", [])

    relevant_matches = []
    for match in all_matches:
        if match.get("status") == "completed":
            team_a = match.get("teams", {}).get("a", {}).get("name", "").lower()
            team_b = match.get("teams", {}).get("b", {}).get("name", "").lower()
            match_title = match.get("name", "").lower()

            if team_name.lower() in team_a or team_name.lower() in team_b or team_name.lower() in match_title:
                start_at = match.get("start_at")
                winner_key = match.get("winner")  # 'a' or 'b'

                if start_at:
                    start_at_human = convert_unix_to_ist(start_at).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    start_at_human = None

                winner_name = None
                if winner_key and winner_key in match.get("teams", {}):
                    winner_name = match["teams"][winner_key]["name"]

                relevant_matches.append({
                    "name": match.get("name"),
                    "status": "completed",
                    "winner": winner_name,
                    "start_at_human": start_at_human
                })
    last_five = sorted(relevant_matches, key=lambda m: m.get("start_at_human") or "", reverse=True)[:5]
    return last_five




def get_head_to_head_matches(team1, team2):
    token = token_create_or_get()
    if not token:
        print("❌ Failed to retrieve token.")
        return []

    conn = http.client.HTTPSConnection("api.sports.roanuz.com")
    headers = {
        'rs-token': token
    }

    conn.request("GET", f"/v5/cricket/{CRICKET_PROJECT_ID}/featured-matches-2/", '', headers)
    res = conn.getresponse()
    data = res.read()
    response_json = json.loads(data.decode("utf-8"))

    all_matches = response_json.get("data", {}).get("matches", [])

    team1 = team1.lower()
    team2 = team2.lower()

    h2h_matches = []
    for match in all_matches:
        if match.get("status") != "completed":
            continue

        match_name = match.get("name", "").lower()
        # Check if both teams are in the match name
        if team1 in match_name and team2 in match_name:
            start_at = match.get("start_at")
            winner_key = match.get("winner")

            start_at_human = (
                convert_unix_to_ist(start_at).strftime('%Y-%m-%d %H:%M:%S')
                if start_at else None
            )

            winner_name = None
            if winner_key and winner_key in match.get("teams", {}):
                winner_name = match["teams"][winner_key]["name"]

            h2h_matches.append({
                "name": match.get("name"),
                "status": "completed",
                "winner": winner_name,
                "start_at_human": start_at_human
            })

    # Optional: sort by start date descending
    h2h_matches.sort(key=lambda m: m.get("start_at_human") or "", reverse=True)

    return h2h_matches



# matches = get_last_five_matches("Australia")
# print(json.dumps(matches, indent=2))

# matches = get_head_to_head_matches("West Indies", "Australia")
# print(json.dumps(matches, indent=2))

# # Example usage
matches = get_featured_matches("2025-07-09")
print(json.dumps(matches, indent=2))
