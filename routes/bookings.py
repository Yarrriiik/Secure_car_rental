from datetime import datetime

from flask import Blueprint, jsonify, request

from db import get_connection
from security.auth_utils import require_role

bookings_bp = Blueprint("bookings", __name__)


@bookings_bp.route("/bookings", methods=["POST"])
@require_role("USER", "MANAGER", "ADMIN")
def create_booking(current_user):
    data = request.get_json() or {}
    car_id = data.get("car_id")
    start_date_raw = data.get("start_date")
    end_date_raw = data.get("end_date")

    if not car_id or not start_date_raw or not end_date_raw:
        return jsonify({"error": "car_id, start_date, end_date required"}), 400

    try:
        start_date = datetime.fromisoformat(start_date_raw).date()
        end_date = datetime.fromisoformat(end_date_raw).date()
    except ValueError:
        return jsonify({"error": "invalid date format, use YYYY-MM-DD"}), 400

    if start_date > end_date:
        return jsonify({"error": "start_date must be <= end_date"}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, status FROM cars
            WHERE id = %s
            """,
            (car_id,),
        )
        car = cur.fetchone()
        if car is None:
            return jsonify({"error": "car not found"}), 404
        if car["status"] != "AVAILABLE":
            return jsonify({"error": "car not available"}), 400

        cur.execute(
            """
            SELECT id FROM bookings
            WHERE car_id = %s
              AND status IN ('PENDING', 'APPROVED')
              AND start_date <= %s
              AND end_date >= %s
            LIMIT 1
            """,
            (car_id, end_date, start_date),
        )
        if cur.fetchone() is not None:
            return jsonify({"error": "booking dates conflict"}), 409

        cur.execute(
            """
            INSERT INTO bookings (user_id, car_id, start_date, end_date, status)
            VALUES (%s, %s, %s, %s, 'PENDING')
            RETURNING id
            """,
            (current_user["id"], car_id, start_date, end_date),
        )
        booking_id = cur.fetchone()["id"]
        conn.commit()
        return jsonify({"status": "ok", "booking_id": booking_id}), 201
    finally:
        cur.close()
        conn.close()


@bookings_bp.route("/bookings/my", methods=["GET"])
@require_role("USER", "MANAGER", "ADMIN")
def my_bookings(current_user):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT b.id, b.car_id, c.model, c.plate_number,
                   b.start_date, b.end_date, b.status
            FROM bookings b
            JOIN cars c ON c.id = b.car_id
            WHERE b.user_id = %s
            ORDER BY b.created_at DESC
            """,
            (current_user["id"],),
        )
        return jsonify(cur.fetchall()), 200
    finally:
        cur.close()
        conn.close()


@bookings_bp.route("/bookings", methods=["GET"])
@require_role("MANAGER", "ADMIN")
def all_bookings(current_user):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT b.id, u.username, c.model, c.plate_number,
                   b.start_date, b.end_date, b.status
            FROM bookings b
            JOIN users u ON u.id = b.user_id
            JOIN cars c ON c.id = b.car_id
            ORDER BY b.created_at DESC
            """
        )
        return jsonify(cur.fetchall()), 200
    finally:
        cur.close()
        conn.close()


@bookings_bp.route("/bookings/<int:booking_id>/status", methods=["PUT"])
@require_role("MANAGER", "ADMIN")
def update_booking_status(booking_id, current_user):
    data = request.get_json() or {}
    status = data.get("status")

    if status not in ("PENDING", "APPROVED", "CANCELLED", "FINISHED"):
        return jsonify({"error": "invalid status"}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, car_id, status
            FROM bookings
            WHERE id = %s
            """,
            (booking_id,),
        )
        booking = cur.fetchone()
        if booking is None:
            return jsonify({"error": "booking not found"}), 404

        current_status = booking["status"]
        if current_status in ("CANCELLED", "FINISHED") and status == "PENDING":
            return jsonify({"error": "cannot move finished/cancelled booking back to pending"}), 400

        cur.execute("UPDATE bookings SET status = %s WHERE id = %s", (status, booking_id))

        if status == "APPROVED":
            cur.execute("UPDATE cars SET status = 'BOOKED' WHERE id = %s", (booking["car_id"],))
        elif status in ("CANCELLED", "FINISHED"):
            cur.execute("UPDATE cars SET status = 'AVAILABLE' WHERE id = %s", (booking["car_id"],))

        conn.commit()
        return jsonify({"status": "ok"}), 200
    finally:
        cur.close()
        conn.close()
