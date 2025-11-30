# routes/bookings.py
from flask import Blueprint, request, jsonify

from db import get_connection
from security.auth_utils import require_role

bookings_bp = Blueprint("bookings", __name__)


@bookings_bp.route("/bookings", methods=["POST"])
@require_role("USER", "MANAGER", "ADMIN")
def create_booking(current_user):
    data = request.get_json()
    car_id = data.get("car_id")
    start_date = data.get("start_date")
    end_date = data.get("end_date")

    if not car_id or not start_date or not end_date:
        return jsonify({"error": "car_id, start_date, end_date required"}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        # Проверяем, что машина существует и доступна
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

        # Создаём бронь со статусом PENDING для текущего пользователя
        cur.execute(
            """
            INSERT INTO bookings (user_id, car_id, start_date, end_date, status)
            VALUES (%s, %s, %s, %s, 'PENDING')
            RETURNING id
            """,
            (current_user["id"], car_id, start_date, end_date),
        )
        booking_id = cur.fetchone()["id"]

        # Машину переводим в BOOKED
        cur.execute(
            "UPDATE cars SET status = 'BOOKED' WHERE id = %s",
            (car_id,),
        )

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
        rows = cur.fetchall()
        return jsonify(rows), 200
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
        rows = cur.fetchall()
        return jsonify(rows), 200
    finally:
        cur.close()
        conn.close()


@bookings_bp.route("/bookings/<int:booking_id>/status", methods=["PUT"])
@require_role("MANAGER", "ADMIN")
def update_booking_status(booking_id, current_user):
    data = request.get_json()
    status = data.get("status")

    if status not in ("PENDING", "APPROVED", "CANCELLED", "FINISHED"):
        return jsonify({"error": "invalid status"}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        # Находим бронь
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

        # Обновляем статус брони
        cur.execute(
            "UPDATE bookings SET status = %s WHERE id = %s",
            (status, booking_id),
        )

        # Если бронь отменена или завершена — освободим машину
        if status in ("CANCELLED", "FINISHED"):
            cur.execute(
                "UPDATE cars SET status = 'AVAILABLE' WHERE id = %s",
                (booking["car_id"],),
            )

        conn.commit()
        return jsonify({"status": "ok"}), 200
    finally:
        cur.close()
        conn.close()
