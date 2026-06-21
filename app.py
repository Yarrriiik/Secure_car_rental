import os

from flask import Flask, jsonify, redirect

from db import get_connection
from routes.auth import auth_bp
from routes.bookings import bookings_bp
from routes.cars import cars_bp


def create_app() -> Flask:
    application = Flask(__name__, static_folder="static", static_url_path="")
    application.register_blueprint(auth_bp)
    application.register_blueprint(cars_bp)
    application.register_blueprint(bookings_bp)

    @application.route("/", methods=["GET"])
    def index():
        return redirect("/login.html")

    @application.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"}), 200

    @application.route("/health/db", methods=["GET"])
    def health_db():
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT 1;")
            row = cur.fetchone()
            cur.close()
            conn.close()
            return jsonify({"db": "ok", "result": row}), 200
        except Exception as exc:
            return jsonify({"db": "error", "error": str(exc)}), 500

    return application


app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_HOST", "0.0.0.0"),
        port=int(os.getenv("FLASK_PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
    )
