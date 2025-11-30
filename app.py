from flask import Flask, jsonify, redirect

from db import get_connection
from routes.auth import auth_bp
from routes.cars import cars_bp
from routes.bookings import bookings_bp

app = Flask(__name__, static_folder="static", static_url_path="")

app.register_blueprint(auth_bp)
app.register_blueprint(cars_bp)
app.register_blueprint(bookings_bp)


@app.route("/", methods=["GET"])
def index():
    return redirect("/login.html")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/health/db", methods=["GET"])
def health_db():
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        row = cur.fetchone()
        cur.close()
        conn.close()
        return jsonify({"db": "ok", "result": row}), 200
    except Exception as e:
        return jsonify({"db": "error", "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
