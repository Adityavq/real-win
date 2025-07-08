import psycopg2
import os

# Load secrets from environment variables. Set these in your .env file or system environment.
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
API_TOKEN = os.getenv('API_TOKEN')

CRICKET_API_KEY = os.getenv("CRICKET_API_KEY")
CRICKET_PROJECT_ID = os.getenv("CRICKET_PROJECT_ID")

# Database configuration: load from environment, fallback to local defaults
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'realwin')
print(DB_NAME)
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'A@ditya3815')
DB_PORT = int(os.getenv('DB_PORT', 5432))

def db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT
    )