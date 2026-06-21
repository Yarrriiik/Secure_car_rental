import os

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

load_dotenv()


def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "secure_car_rental"),
        user=os.getenv("DB_USER", "car_rental_user"),
        password=os.getenv("DB_PASSWORD", "car_rental_password"),
        cursor_factory=RealDictCursor,
    )
