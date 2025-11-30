# security/session.py
from datetime import datetime, timedelta
import secrets

from db import get_connection

SESSION_LIFETIME_HOURS = 2


def create_session(user_id: int, ip_address: str, user_agent: str) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=SESSION_LIFETIME_HOURS)

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO sessions (user_id, token, ip_address, user_agent, expires_at)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user_id, token, ip_address, user_agent, expires_at),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

    return token
