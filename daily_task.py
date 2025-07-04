from main import app
from main import run_and_store_all_today_predictions 


with app.app_context():
    run_and_store_all_today_predictions()
    print("Daily predictions updated.")
    