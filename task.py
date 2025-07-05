import os
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from models import Team, Match, Prediction, TopPrediction 
from fotball import (
    fetch_all_matches_for_date,
    get_participant_team_ids,
    gpt_chatbot,
    parse_gpt_prediction,
)
from livematches import get_team_logo

# Load environment variables
load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT")

DATABASE_URI = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'

# SQLAlchemy setup
engine = create_engine(DATABASE_URI)
Session = scoped_session(sessionmaker(bind=engine))
session = Session()

predictions_cache = {}

def run_and_store_all_today_predictions():
    global predictions_cache
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        matches = fetch_all_matches_for_date(today)
        predictions = []
        league_cache = {}
        notes = "Automated prediction for all matches of the day."

        for match in matches[:6]:
            fixture_id = match.get("id")
            starting_at = match.get("starting_at")
            if not fixture_id or not starting_at:
                continue

            participant_data = get_participant_team_ids(fixture_id)
            if not participant_data:
                continue

            team_id_A = participant_data["team_a_id"]
            team_id_B = participant_data["team_b_id"]

            team_a = session.query(Team).filter_by(id=team_id_A).first()
            if not team_a:
                team_a_name = f"Team {team_id_A}"
                team_a_logo = get_team_logo(team_a_name)
                team_a = Team(id=team_id_A, name=team_a_name, logo_url=team_a_logo)
                session.add(team_a)

            team_b = session.query(Team).filter_by(id=team_id_B).first()
            if not team_b:
                team_b_name = f"Team {team_id_B}"
                team_b_logo = get_team_logo(team_b_name)
                team_b = Team(id=team_id_B, name=team_b_name, logo_url=team_b_logo)
                session.add(team_b)

            session.flush()

            match_obj = session.query(Match).filter_by(id=fixture_id).first()
            if not match_obj:
                match_obj = Match(id=fixture_id, team1_id=team_id_A, team2_id=team_id_B, date=today)
                session.add(match_obj)

            session.flush()

            try:
                match_date = datetime.strptime(starting_at, "%Y-%m-%d %H:%M:%S").strftime("%d-%m-%Y")
            except Exception:
                match_date = starting_at

            prediction_str = gpt_chatbot(team_id_A, team_id_B, match_date, notes, league_cache)
            prediction_data = parse_gpt_prediction(prediction_str)

            predicted_winner_name = prediction_data.get("predicted_winner")
            predicted_winner = session.query(Team).filter_by(name=predicted_winner_name).first()
            if not predicted_winner:
                predicted_winner_logo = get_team_logo(predicted_winner_name)
                predicted_winner = Team(name=predicted_winner_name, logo_url=predicted_winner_logo)
                session.add(predicted_winner)

            session.flush()

            confidence = float(prediction_data.get("win_probability", 0))
            pred = Prediction(
                match_id=fixture_id,
                confidence=confidence,
                predicted_winner_id=predicted_winner.id,
                data_points=prediction_str,
                created_at=datetime.utcnow()
            )
            session.add(pred)
            session.flush()

            prediction_data.update({
                "fixture_id": fixture_id,
                "starting_at": starting_at,
                "raw_gpt_response": prediction_str,
                "db_prediction_id": pred.id
            })
            predictions.append(prediction_data)

        # Remove existing top predictions for today
        today_date = datetime.now().date()
        session.query(TopPrediction).filter_by(date=today_date).delete()
        session.commit()

        # Save top 3 predictions
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
            session.add(top_pred)

        session.commit()
        predictions_cache = {
            "status": "success",
            "date": today,
            "predictions": predictions,
            "top3": unique_preds
        }

    except Exception as e:
        session.rollback()
        predictions_cache = {"status": "error", "message": str(e)}
        print("Error occurred:", str(e))


if __name__ == "__main__":
    run_and_store_all_today_predictions()
