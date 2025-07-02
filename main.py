from flask import Flask, jsonify, session
import requests
from livematches import fetch_today_football_fixtures, fetch_today_matches_with_team_info
from flask import Flask, g, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import config
import os
from flask import redirect, url_for
from functools import wraps
from flask import Flask, render_template
from config import db_connection
from fotball import  get_participant_team_ids, gpt_chatbot, get_top5_predictions_for_date, fetch_all_matches_for_date, parse_gpt_prediction
from datetime import datetime
from models import db  # Import SQLAlchemy db instance
from urllib.parse import quote_plus

app = Flask(__name__)
app.secret_key = 'e3c2d2a1bb4a6e34f2e2b6a30d7c9af41e2f96c8595c8c7a623ebd47d8df0f30'

# SQLAlchemy configuration for PostgreSQL
password = quote_plus(config.DB_PASSWORD)
app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{config.DB_USER}:{password}@{config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('sigin_page')) 
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def signup_page():
    return render_template('signup.html')

@app.route('/signin')
def sigin_page():
    return render_template('login.html')

@app.route('/select-match')
@login_required
def select_match_page():
    return render_template('select_match.html')

@app.route('/home')
@login_required
def home_page():
    if 'selected_fixture_id' not in session:
        return redirect(url_for('select_match_page'))
    return render_template('index.html')

@app.route('/logout')
def logout():
    session.pop('user_email', None)
    return redirect(url_for('sigin_page'))

@app.route('/api/today-matches-list', methods=['GET'])
@login_required
def today_matches_list():
    matches = fetch_today_matches_with_team_info()
    return jsonify(matches)

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.json
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    hashed_password = generate_password_hash(password)
    conn = db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (email, password, name) VALUES (%s, %s, %s)",
            (email, hashed_password, username)
        )
        conn.commit()
        return jsonify({'message': 'User registered successfully', 'redirect': url_for('select_match_page')}), 201
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return jsonify({'error': 'Email already exists'}), 409
    finally:
        cur.close()
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    try:
        conn = db_connection()
        cur = conn.cursor()
        cur.execute("SELECT password FROM users WHERE email = %s", (email,))
        result = cur.fetchone()
        cur.close()
        conn.close()
        if result:
            hashed_password = result[0]
            if check_password_hash(hashed_password, password):
                session['user_email'] = email 
                return jsonify({'message': 'Login successful', 'redirect': url_for('select_match_page')}), 200
            else:
                return jsonify({'error': 'Invalid Authentication'}), 401
        else:
            return jsonify({'error': 'Email not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/select-match', methods=['POST'])
@login_required
def set_selected_match():
    data = request.json
    fixture_id = data.get('fixture_id')
    if not fixture_id:
        return jsonify({'error': 'No fixture selected'}), 400
    session['selected_fixture_id'] = fixture_id
    return jsonify({'message': 'Match selected', 'redirect': url_for('home_page')})

@app.route("/api/today-football-matches", methods=["GET"])
def predict_first_today_match():
    try:
        matches = fetch_today_football_fixtures()

        if not matches["today_matches"]:
            return jsonify({"status": "error", "message": "No matches found today"}), 404

        first_match = matches["today_matches"][0]
        fixture_id = first_match["id"]
        starting_at = first_match["starting_at"]

        # Convert ISO timestamp to readable date if needed (optional)
        match_date = datetime.strptime(starting_at, "%Y-%m-%d %H:%M:%S").strftime("%d-%m-%Y")

        participant_data = get_participant_team_ids(fixture_id)

        if not participant_data:
            return jsonify({"status": "error", "message": "Failed to retrieve team IDs"}), 500

        team_id_A = participant_data["team_a_id"]
        team_id_B = participant_data["team_b_id"]
        notes = "Automated prediction based on today's first match context."
        league_cache = {}

        # Run GPT Prediction
        prediction_result = gpt_chatbot(team_id_A, team_id_B, match_date, notes, league_cache)

        return jsonify({
            "status": "success",
            "fixture": {
                "id": fixture_id,
                "starting_at": starting_at
            },
            "prediction": prediction_result
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/top5-today-predictions", methods=["GET"])
def top5_today_predictions():
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        top5 = get_top5_predictions_for_date(today)
        return jsonify({
            "status": "success",
            "date": today,
            "top5_predictions": top5
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/fixture-details/<int:fixture_id>', methods=['GET'])
@login_required
def fixture_details(fixture_id):
    api_token = os.getenv("API_TOKEN") or "YOUR_API_TOKEN"
    url = f"https://api.sportmonks.com/v3/football/fixtures/{fixture_id}?api_token={api_token}&include=participants"
    res = requests.get(url)
    data = res.json()
    participants = data.get("data", {}).get("participants", [])
    if len(participants) >= 2:
        home = participants[0]
        away = participants[1]
        return jsonify({
            "home_team": home.get("name"),
            "home_logo": home.get("image_path"),
            "away_team": away.get("name"),
            "away_logo": away.get("image_path"),
            "starting_at": data.get("data", {}).get("starting_at"),
            "fixture_id": fixture_id
        })
    return jsonify({"error": "Participants not found"}), 404

@app.route("/api/all-today-predictions", methods=["GET"])
def all_today_predictions():
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        matches = fetch_all_matches_for_date(today)
        print(f"Found {len(matches)} matches for today")
        predictions = []
        league_cache = {}
        notes = "Automated prediction for all matches of the day."
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
                match_date = datetime.strptime(starting_at, "%Y-%m-%d %H:%M:%S").strftime("%d-%m-%Y")
            except Exception:
                match_date = starting_at
            prediction_str = gpt_chatbot(team_id_A, team_id_B, match_date, notes, league_cache)
            prediction = parse_gpt_prediction(prediction_str)
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
        return jsonify({
            "status": "success",
            "date": today,
            "predictions": predictions
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
