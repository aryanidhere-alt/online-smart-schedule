import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():

    connection = psycopg2.connect(
        host=os.environ.get("DB_HOST"),
        port=int(os.environ.get("DB_PORT", "5432")),
        database=os.environ.get("DB_NAME"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD")
    )

    return connection 

