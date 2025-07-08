import requests
from datetime import datetime
from datetime import datetime, timezone
from dotenv import load_dotenv
import os
import http.client
import json
import urllib.parse
from openai import OpenAI
from config import OPENAI_API_KEY


load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
client = OpenAI(api_key=OPENAI_API_KEY)

BASE_URL_FOOTBALL = "https://api.sportmonks.com/v3/football/fixtures"
BASE_URL = "api.sportmonks.com"


def fetch_api(endpoint, is_full_url=False):
    conn = http.client.HTTPSConnection(BASE_URL)
    if is_full_url:
        conn.request("GET", f"{endpoint}&api_token={API_TOKEN}")
    else:
        conn.request("GET", f"{endpoint}?api_token={API_TOKEN}")
    res = conn.getresponse()
    raw = res.read()
    conn.close()
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        print("❌ Invalid JSON response received from:", endpoint)
        print("Raw response:", raw)
        return {}


def get_league_name(league_id, cache):
    if league_id in cache:
        return cache[league_id]
    try:
        league_data = fetch_api(f"/v3/football/leagues/{league_id}")
        name = league_data.get("data", {}).get("name")
        if name:
            cache[league_id] = name
        return name
    except Exception as e:
        print(f"Failed to fetch league {league_id}: {e}")
        return None


def get_team_details_with_last_five_matches(team_id, league_cache):
    # 1. Get Team Details
    team_data = fetch_api(f"/v3/football/teams/{team_id}")
    team_info = team_data.get("data", {})
    team_name = team_info.get("name", "")

    # 2. Get Venue Info
    venue_info = {}
    venue_id = team_info.get("venue_id")
    if venue_id:
        venue_data = fetch_api(f"/v3/football/venues/{venue_id}")
        venue_info = {
            "venue_id": venue_id,
            "venue_name_ground": venue_data.get("data", {}).get("name"),
            "venue_address_ground": venue_data.get("data", {}).get("address")
        }

    # 3. Get Players
    squad_data = fetch_api(f"/v3/football/squads/teams/{team_id}")
    squad = squad_data.get("data", [])
    players = []
    for player in squad:
        player_id = player["player_id"]
        player_info = fetch_api(f"/v3/football/players/{player_id}")
        player_data = player_info.get("data", {})
        players.append({
            "id": player_id,
            "name": player_data.get("display_name") or player_data.get("common_name"),
            "gender": player_data.get("gender")
        })

    # 4. Get Last 5 Matches with League Name
    last_five_matches = []
    league_ids = set()
    if team_name:
        encoded_name = urllib.parse.quote(team_name)
        search_url = f"/v3/football/fixtures/search/{encoded_name}?order=starting_at.desc&per_page=5"
        fixture_data = fetch_api(search_url, is_full_url=True)
        fixtures = fixture_data.get("data", [])

        for fixture in fixtures:
            league_ids.add(fixture.get("league_id"))
        
        league_position_maps = {
            league_id: get_team_positions_map(league_id)
            for league_id in league_ids
        }

        if fixture_data.get("data"):
            for fixture in fixture_data["data"]:
                league_id = fixture.get("league_id")
                league_name = get_league_name(league_id, league_cache)
                position_map = league_position_maps.get(league_id, {})
                team_position = position_map.get(team_id)
                last_five_matches.append({
                    "fixture_id": fixture.get("id"),
                    "result_info": fixture.get("result_info"),
                    "season_id": fixture.get("season_id"),
                    "league_id": league_id,
                    "league_name": league_name,
                    "leg": fixture.get("leg"),
                    "team_position": team_position
                })
    latest_position = None
    if last_five_matches:
        latest_position = last_five_matches[0].get("team_position")
    # 5. Final response
    return {
        "team_name": team_info.get("name"),
        "last_played_at": team_info.get("last_played_at"),
        "team_id": team_info.get("id"),
        "country_id": team_info.get("country_id"),
        "type": team_info.get("type"),
        "sport_id": team_info.get("sport_id"),
        **venue_info,
        "team_position": latest_position,
        "last_five_matches": last_five_matches,
        "players": players
    }

def get_team_positions_map(league_id):
    """
    Fetches live standings for a league and returns a dictionary:
    {participant_id: position}
    """
    conn = http.client.HTTPSConnection("api.sportmonks.com")
    endpoint = f"/v3/football/standings/live/leagues/{league_id}?api_token={API_TOKEN}"
    conn.request("GET", endpoint)
    res = conn.getresponse()
    if res.status != 200:
        print(f"Error: HTTP {res.status}")
        return {}

    data = res.read()
    try:
        standings_data = json.loads(data.decode("utf-8")).get("data", [])
        return {entry["participant_id"]: entry["position"] for entry in standings_data}
    except Exception as e:
        print("Failed to process JSON:", e)
        return {}


def get_head_to_head(team_id_1, team_id_2):
    """
    Fetches the last 3 head-to-head fixtures between two teams from the Sportmonks API.
    Returns a list of dicts with basic match info.
    """
    url = f"https://api.sportmonks.com/v3/football/fixtures/head-to-head/{team_id_1}/{team_id_2}"
    params = {
        "api_token": API_TOKEN
    }
    try:
        response = requests.get(url, params=params)
        if response.status_code != 200:
            print(f"Failed to fetch head-to-head data: {response.status_code}")
            return []
        data = response.json().get("data", [])
        sorted_data = sorted(data, key=lambda x: x.get("starting_at", ""), reverse=True)
        return [
            {
                "fixture_id": match.get("id"),
                "date": match.get("starting_at"),
                "result_info": match.get("result_info"),
                "league_name": match.get("league", {}).get("name", "Unknown League")
            }
            for match in sorted_data[:3]
        ]
    except Exception as e:
        print(f"Error fetching head-to-head: {e}")
        return []


def gpt_chatbot(team_id_A, team_id_B, match_date, notes, league_cache):
    team_A_data = get_team_details_with_last_five_matches(team_id_A, league_cache)
    team_B_data = get_team_details_with_last_five_matches(team_id_B, league_cache)

    match_title = f"{team_A_data['team_name']} vs {team_B_data['team_name']}"
    venue = team_A_data.get("venue_name_ground", "Unknown Venue")
    venue_address = team_A_data.get("venue_address_ground", "Unknown Venue")
    league = team_A_data.get("league_name", "Unknown League")
    kickoff_time = match_date
    timezone = "UTC"  # You can update this if you have timezone info
    team_A_position = team_A_data.get("team_position")
    team_B_position = team_B_data.get("team_position")

    def format_matches(matches):
        return ", ".join([
            f"{m.get('result_info', 'No result')} ({m.get('league_name', 'Unknown League')})"
            for m in matches
        ])

    team_a_form = format_matches(team_A_data['last_five_matches'])
    team_b_form = format_matches(team_B_data['last_five_matches'])
    
    # Fetch head-to-head data for the last 3 meetings
    head_to_head_matches = get_head_to_head(team_id_A, team_id_B)
    if head_to_head_matches:
        head_to_head = format_matches(head_to_head_matches)
    else:
        head_to_head = "N/A"

    injuries = "None"      # You can fetch and format if you have this data
    standings = f"Team A standing : {team_A_position} and Team B standing : {team_B_position}"     # You can fetch and format if you have this data

    # Print all stats for debugging
    print("\n===== MATCH STATS FOR GPT PREDICTION =====")
    print(f"Match: {match_title}")
    print(f"League: {league}")
    print(f"Venue: {venue} ({venue_address})")
    print(f"Kickoff Time: {kickoff_time} {timezone}")
    print(f"Team A: {team_A_data['team_name']}")
    print(f"  Last 5 Matches: {team_a_form}")
    print(f"Team B: {team_B_data['team_name']}")
    print(f"  Last 5 Matches: {team_b_form}")
    print(f"Recent Head-to-Head: {head_to_head}")
    print(f"Injuries: {injuries}")
    print(f"League Standings: {standings}")
    print("========================================\n")

    final_prompt = f'''You are an expert AI sports analyst. Based on the structured data provided below, return a single JSON object with your most confident football betting prediction for today’s matches. Use all available datapoints—team form, standings, player info, venue, head-to-head stats, win probability, injuries, and any other relevant indicators—to arrive at your pick. Be highly analytical.
 
Provide your explanation as an array of at least 4 detailed bullet points.
 
Use the following JSON format (snake_case keys, no extra text or markdown):
 
{{
  "fixture": "<team_a> vs <team_b>",
  "predicted_winner": "<team_name>",
  "win_probability": <number>,      // percentage 0-100
  "confidence_level": "<High|Medium|Low>",
  "explanation": [
    "<Bullet point #1>",
    "<Bullet point #2>",
    "<Bullet point #3>",
    "<Bullet point #4>",
    // (add more if needed)
  ],
  "kickoff_time": "<YYYY-MM-DD HH:MM:SS UTC>"
}}
Only output the JSON object, with no extra text or markdown. Use snake_case for all keys. Do no+6
t include cricket or any placeholder data.

Structured data:
- Match: {match_title}
- League: {league}
- Team Form (Last 5 games):
  - {team_A_data['team_name']}: {team_a_form}
  - {team_B_data['team_name']}: {team_b_form}
- Recent Head-to-Head (last 3 meetings): {head_to_head}
- Injuries (if available): {injuries}
- League Standings: {standings}
- Match Start Time: {kickoff_time} {timezone}
'''
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a smart football analytics assistant."},
            {"role": "user", "content": final_prompt.strip()}
        ],
        temperature=0.7,
        max_tokens=500
    )
    gpt_response = response.choices[0].message.content.strip()
    print("===== GPT PREDICTION RESULT =====")
    print(gpt_response)
    print("=================================")
    # Post-process to ensure all required fields are present
    import json, re
    try:
        match = re.search(r'\{.*\}', gpt_response, re.DOTALL)
        if match:
            prediction_json = json.loads(match.group(0))
        else:
            prediction_json = {}
    except Exception as e:
        print(f"Failed to parse GPT prediction: {e}")
        prediction_json = {}
    # Ensure all required fields
    required_fields = [
        "fixture", "predicted_winner", "win_probability", "confidence_level", "explanation", "kickoff_time"
    ]
    for field in required_fields:
        if field not in prediction_json or prediction_json[field] in [None, ""]:
            prediction_json[field] = "-"
    return json.dumps(prediction_json)


def get_participant_team_ids(fixture_id):
    url = f"https://api.sportmonks.com/v3/football/fixtures/{fixture_id}"
    params = {
        "api_token": API_TOKEN,
        "include": "participants"
    }

    response = requests.get(url, params=params)

    if response.status_code != 200:
        print("Failed to fetch data:", response.status_code)
        return None

    try:
        data = response.json()
        participants = data.get("data", {}).get("participants", [])

        team_ids = [team["id"] for team in participants]

        if len(team_ids) == 2:
            return {
                "team_a_id": team_ids[0],
                "team_b_id": team_ids[1]
            }
        else:
            print("Unexpected number of participants.")
            return None

    except Exception as e:
        print("Error:", e)
        return None

def fetch_all_matches_for_date(date_str):
    base_url = f"https://api.sportmonks.com/v3/football/fixtures/date/{date_str}"
    all_matches = []
    page = 1

    while True:
        url = f"{base_url}?api_token={API_TOKEN}&page={page}"
        print("Fetching:", url)

        response = requests.get(url)
        if response.status_code != 200:
            print(f"Failed to fetch matches: {response.status_code}")
            break

        data = response.json()

        matches = data.get("data", [])
        all_matches.extend(matches)

        pagination = data.get("pagination", {})
        print("Pagination info:", pagination)

        if pagination.get("has_more", False):
            page = pagination.get("current_page", 1) + 1
        else:
            break

    return all_matches


def parse_gpt_prediction(prediction_str):
    """
    Parse the GPT prediction JSON string and extract confidence/win probability.
    Returns a dict with keys: winner, prediction, confidence, probability, reasoning.
    """
    try:
        import re, json
        match = re.search(r'\{.*\}', prediction_str, re.DOTALL)
        if match:
            prediction_json = json.loads(match.group(0))
            return prediction_json
    except Exception as e:
        print(f"Failed to parse GPT prediction: {e}")
    return {}


def get_top5_predictions_for_date(date_str, notes="Automated prediction for all matches of the day."):
    """
    For all matches on the given date, get predictions and return the top 5 by confidence/probability.
    """
    matches = fetch_all_matches_for_date(date_str)
    predictions = []
    league_cache = {}
    for match in matches:
        fixture_id = match.get("id")
        starting_at = match.get("starting_at")
        if not fixture_id or not starting_at:
            continue
        participant_data = get_participant_team_ids(fixture_id)
        if not participant_data:
            continue
        team_id_A = participant_data["team_a_id"]
        team_id_B = participant_data["team_b_id"]
        try:
            # match_date = datetime.strptime(starting_at, "%Y-%m-%d %H:%M:%S").strftime("%d-%m-%Y")
            dt = datetime.strptime(starting_at, "%Y-%m-%d %H:%M:%S")
            match_date = dt.strftime("%d-%m-%Y %H:%M")
        except Exception:
            match_date = starting_at
        # Get prediction
        prediction_str = gpt_chatbot(team_id_A, team_id_B, match_date, notes, league_cache)
        prediction = parse_gpt_prediction(prediction_str)
        # Attach fixture info for context
        prediction["fixture_id"] = fixture_id
        prediction["starting_at"] = starting_at
        prediction["raw_gpt_response"] = prediction_str
        predictions.append(prediction)
    def get_sort_key(pred):
        prob = pred.get("A win probability estimate (in %)") or pred.get("win_probability")
        try:
            return float(str(prob).replace("%", ""))
        except:
            conf = (pred.get("Confidence") or pred.get("confidence") or "").lower()
            return {"high": 100, "medium": 60, "low": 30}.get(conf, 0)
    predictions.sort(key=get_sort_key, reverse=True)
    return predictions[:5]
