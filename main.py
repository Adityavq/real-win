from flask import Flask, jsonify, session
import requests
from livematches import fetch_today_football_fixtures, fetch_today_matches_with_team_info, get_team_logo
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
from models import Team, Match, Prediction, TopPrediction
from flask_migrate import Migrate

app = Flask(__name__)
app.secret_key = 'e3c2d2a1bb4a6e34f2e2b6a30d7c9af41e2f96c8595c8c7a623ebd47d8df0f30'

password = quote_plus(config.DB_PASSWORD)
app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{config.DB_USER}:{password}@{config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()

migrate = Migrate(app, db)

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
    from models import TopPrediction, Prediction, Match, Team
    today = datetime.now().strftime('%Y-%m-%d')
    top_preds = TopPrediction.query.filter_by(date=today).all()
    matches = []
    for top_pred in top_preds:
        pred = Prediction.query.get(top_pred.prediction_id)
        match = Match.query.get(pred.match_id)
        team1 = Team.query.get(match.team1_id)
        team2 = Team.query.get(match.team2_id)
        matches.append({
            'fixture_id': match.id,
            'team1_id': team1.id,
            'team1_name': team1.name,
            'team2_id': team2.id,
            'team2_name': team2.name,
            'date': str(match.date)
        })
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
        predictions = []
        league_cache = {}
        notes = "Automated prediction for all matches of the day."
        matches = matches[:1]
        for match in matches:
            fixture_id = match.get("id")
            starting_at = match.get("starting_at")
            if not fixture_id or not starting_at:
                continue
            participant_data = get_participant_team_ids(fixture_id)
            print("participant_data",participant_data)
            if not participant_data:
                continue
            team_id_A = participant_data["team_a_id"]
            team_id_B = participant_data["team_b_id"]
            team_a = Team.query.filter_by(id=team_id_A).first()
            if not team_a:
                team_a_name = f"Team {team_id_A}"
                team_a_logo = get_team_logo(team_a_name)
                team_a = Team(id=team_id_A, name=team_a_name, logo_url=team_a_logo)
                db.session.add(team_a)
            team_b = Team.query.filter_by(id=team_id_B).first()
            if not team_b:
                team_b_name = f"Team {team_id_B}"
                team_b_logo = get_team_logo(team_b_name)
                team_b = Team(id=team_id_B, name=team_b_name, logo_url=team_b_logo)
                db.session.add(team_b)
            db.session.flush()
            match_obj = Match.query.filter_by(id=fixture_id).first()
            if not match_obj:
                match_obj = Match(id=fixture_id, team1_id=team_id_A, team2_id=team_id_B, date=today)
                db.session.add(match_obj)
            db.session.flush()
            # Get prediction
            try:
                match_date = datetime.strptime(starting_at, "%Y-%m-%d %H:%M:%S").strftime("%d-%m-%Y")
            except Exception:
                match_date = starting_at
            prediction_str = gpt_chatbot(team_id_A, team_id_B, match_date, notes, league_cache)
            prediction_data = parse_gpt_prediction(prediction_str)
            # Save Prediction
            predicted_winner_name = prediction_data.get("predicted_winner")
            predicted_winner = Team.query.filter_by(name=predicted_winner_name).first()
            if not predicted_winner:
                predicted_winner_logo = get_team_logo(predicted_winner_name)
                predicted_winner = Team(name=predicted_winner_name, logo_url=predicted_winner_logo)
                db.session.add(predicted_winner)
            db.session.flush()
            confidence = float(prediction_data.get("win_probability", 0))
            pred = Prediction(
                match_id=fixture_id,
                confidence=confidence,
                predicted_winner_id=predicted_winner.id,
                data_points=str(prediction_data)
            )
            db.session.add(pred)
            db.session.flush()
            prediction_data["fixture_id"] = fixture_id
            prediction_data["starting_at"] = starting_at
            prediction_data["raw_gpt_response"] = prediction_str
            prediction_data["db_prediction_id"] = pred.id
            predictions.append(prediction_data)
            
        # Sort and save top 3 predictions
        predictions.sort(key=lambda x: float(x.get("win_probability", 0)), reverse=True)
        top3 = predictions[:5]
        for pred_data in top3:
            top_pred = TopPrediction(
                prediction_id=pred_data["db_prediction_id"],
                date=today
            )
            db.session.add(top_pred)
        db.session.commit()
        return jsonify({
            "status": "success",
            "date": today,
            "predictions": predictions,
            "top3": top3
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

def run_and_store_all_today_predictions():
    global predictions_cache
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        matches = fetch_all_matches_for_date(today)
        predictions = []
        league_cache = {}
        notes = "Automated prediction for all matches of the day."
        matches = matches[:4]
        for match in matches:
            fixture_id = match.get("id")
            starting_at = match.get("starting_at")
            if not fixture_id or not starting_at:
                continue
            participant_data = get_participant_team_ids(fixture_id)
            print("participant_data",participant_data)
            if not participant_data:
                continue
            team_id_A = participant_data["team_a_id"]
            team_id_B = participant_data["team_b_id"]
            team_a = Team.query.filter_by(id=team_id_A).first()
            if not team_a:
                team_a_name = f"Team {team_id_A}"
                team_a_logo = get_team_logo(team_a_name)
                team_a = Team(id=team_id_A, name=team_a_name, logo_url=team_a_logo)
                db.session.add(team_a)
            team_b = Team.query.filter_by(id=team_id_B).first()
            if not team_b:
                team_b_name = f"Team {team_id_B}"
                team_b_logo = get_team_logo(team_b_name)
                team_b = Team(id=team_id_B, name=team_b_name, logo_url=team_b_logo)
                db.session.add(team_b)
            db.session.flush()
            match_obj = Match.query.filter_by(id=fixture_id).first()
            if not match_obj:
                match_obj = Match(id=fixture_id, team1_id=team_id_A, team2_id=team_id_B, date=today)
                db.session.add(match_obj)
            db.session.flush()
            # Get prediction
            try:
                match_date = datetime.strptime(starting_at, "%Y-%m-%d %H:%M:%S").strftime("%d-%m-%Y")
            except Exception:
                match_date = starting_at
            prediction_str = gpt_chatbot(team_id_A, team_id_B, match_date, notes, league_cache)
            prediction_data = parse_gpt_prediction(prediction_str)
            # Save Prediction
            predicted_winner_name = prediction_data.get("predicted_winner")
            predicted_winner = Team.query.filter_by(name=predicted_winner_name).first()
            if not predicted_winner:
                predicted_winner_logo = get_team_logo(predicted_winner_name)
                predicted_winner = Team(name=predicted_winner_name, logo_url=predicted_winner_logo)
                db.session.add(predicted_winner)
            db.session.flush()
            confidence = float(prediction_data.get("win_probability", 0))
            pred = Prediction(
                match_id=fixture_id,
                confidence=confidence,
                predicted_winner_id=predicted_winner.id,
                data_points=prediction_str
            )
            db.session.add(pred)
            db.session.flush()
            prediction_data["fixture_id"] = fixture_id
            prediction_data["starting_at"] = starting_at
            prediction_data["raw_gpt_response"] = prediction_str
            prediction_data["db_prediction_id"] = pred.id
            predictions.append(prediction_data)
        # Remove duplicate TopPrediction for the same fixture/date
        today_date = datetime.now().date()
        TopPrediction.query.filter_by(date=today_date).delete()
        db.session.commit()
        # Sort and save top 3 unique predictions
        unique_preds = []
        seen_fixtures = set()
        for pred_data in sorted(predictions, key=lambda x: float(x.get("win_probability", 0)), reverse=True):
            if pred_data["fixture_id"] in seen_fixtures:
                continue
            seen_fixtures.add(pred_data["fixture_id"])
            unique_preds.append(pred_data)
            if len(unique_preds) == 3:
                break
        for pred_data in unique_preds:
            top_pred = TopPrediction(
                prediction_id=pred_data["db_prediction_id"],
                date=today_date
            )
            db.session.add(top_pred)
        db.session.commit()
        predictions_cache = {
            "status": "success",
            "date": today,
            "predictions": predictions,
            "top3": unique_preds
        }
    except Exception as e:
        db.session.rollback()
        predictions_cache = {"status": "error", "message": str(e)}

@app.route('/api/top3-today-predictions-details', methods=['GET'])
def top3_today_predictions_details():
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        top_preds = TopPrediction.query.filter_by(date=today).order_by(TopPrediction.id.desc()).all()
        result = []
        seen_fixtures = set()
        for top_pred in top_preds:
            pred = Prediction.query.get(top_pred.prediction_id)
            match = Match.query.get(pred.match_id)
            if match.id in seen_fixtures:
                continue
            seen_fixtures.add(match.id)
            # Fetch logos from external API as in /api/fixture-details
            api_token = os.getenv("API_TOKEN") or "YOUR_API_TOKEN"
            url = f"https://api.sportmonks.com/v3/football/fixtures/{match.id}?api_token={api_token}&include=participants"
            res = requests.get(url)
            data = res.json()
            participants = data.get("data", {}).get("participants", [])
            home_logo = None
            away_logo = None
            if len(participants) >= 2:
                home_logo = participants[0].get("image_path")
                away_logo = participants[1].get("image_path")
            result.append({
                'fixture_id': match.id,
                'team1': {'id': match.team1_id, 'name': Team.query.get(match.team1_id).name, 'logo_url': home_logo},
                'team2': {'id': match.team2_id, 'name': Team.query.get(match.team2_id).name, 'logo_url': away_logo},
                'prediction': {
                    'predicted_winner': Team.query.get(pred.predicted_winner_id).name if pred.predicted_winner_id else None,
                    'win_probability': pred.confidence,
                    'raw_gpt_response': pred.data_points
                },
                'starting_at': str(match.date)
            })
            if len(result) == 3:
                break
        return jsonify(result)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/prediction-details/<int:fixture_id>', methods=['GET'])
def prediction_details(fixture_id):
    try:
        match = Match.query.get(fixture_id)
        if not match:
            return jsonify({'error': 'Match not found'}), 404
        team1 = Team.query.get(match.team1_id)
        team2 = Team.query.get(match.team2_id)
        pred = Prediction.query.filter_by(match_id=fixture_id).order_by(Prediction.id.desc()).first()
        if not pred:
            return jsonify({'error': 'Prediction not found'}), 404
        predicted_winner = Team.query.get(pred.predicted_winner_id)
        return jsonify({
            'fixture_id': match.id,
            'team1': {'id': team1.id, 'name': team1.name, 'logo_url': team1.logo_url},
            'team2': {'id': team2.id, 'name': team2.name, 'logo_url': team2.logo_url},
            'prediction': {
                'predicted_winner': predicted_winner.name if predicted_winner else None,
                'win_probability': pred.confidence,
                'raw_gpt_response': pred.data_points
            },
            'starting_at': str(match.date)
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/match-details/<int:fixture_id>')
@login_required
def match_details_page(fixture_id):
    return render_template('match_details.html')

if __name__ == "__main__":
    with app.app_context():
        run_and_store_all_today_predictions()
    app.run(debug=True,host='0.0.0.0',port=5000)
