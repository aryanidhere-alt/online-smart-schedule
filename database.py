import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():

    connection = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

    return connection
print("Database connection established successfully.")

import os
import mysql.connector


def get_db_connection():

    return mysql.connector.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", ""),
        database=os.environ.get(
            "DB_NAME",
            "online_smart_schedule"
        ),
        port=int(os.environ.get("DB_PORT", "3306"))
    )