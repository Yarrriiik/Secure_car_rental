from flask import Blueprint, jsonify, request

from db import get_connection
from security.auth_utils import require_role

cars_bp = Blueprint("cars", __name__)


@cars_bp.route("/cars", methods=["GET"])
@require_role("USER", "MANAGER", "ADMIN")
def list_cars(current_user):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, model, plate_number, status, price_per_day
            FROM cars
            ORDER BY id
            """
        )
        return jsonify(cur.fetchall()), 200
    finally:
        cur.close()
        conn.close()


@cars_bp.route("/cars/<int:car_id>", methods=["GET"])
@require_role("USER", "MANAGER", "ADMIN")
def get_car(car_id, current_user):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, model, plate_number, status, price_per_day
            FROM cars
            WHERE id = %s
            """,
            (car_id,),
        )
        row = cur.fetchone()
        if row is None:
            return jsonify({"error": "car not found"}), 404
        return jsonify(row), 200
    finally:
        cur.close()
        conn.close()


@cars_bp.route("/cars", methods=["POST"])
@require_role("ADMIN")
def create_car(current_user):
    data = request.get_json() or {}
    model = data.get("model")
    plate_number = data.get("plate_number")
    price_per_day = data.get("price_per_day")

    if not model or not plate_number or price_per_day is None:
        return jsonify({"error": "model, plate_number, price_per_day required"}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO cars (model, plate_number, price_per_day)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (model, plate_number, price_per_day),
        )
        car_id = cur.fetchone()["id"]
        conn.commit()
        return jsonify({"status": "ok", "car_id": car_id}), 201
    finally:
        cur.close()
        conn.close()


@cars_bp.route("/cars/<int:car_id>/status", methods=["PUT"])
@require_role("MANAGER", "ADMIN")
def update_car_status(car_id, current_user):
    data = request.get_json() or {}
    status = data.get("status")

    if status not in ("AVAILABLE", "BOOKED", "SERVICE"):
        return jsonify({"error": "invalid status"}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE cars
            SET status = %s
            WHERE id = %s
            """,
            (status, car_id),
        )
        if cur.rowcount == 0:
            conn.rollback()
            return jsonify({"error": "car not found"}), 404
        conn.commit()
        return jsonify({"status": "ok"}), 200
    finally:
        cur.close()
        conn.close()
