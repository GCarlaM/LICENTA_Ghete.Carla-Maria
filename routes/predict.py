from flask import Blueprint, jsonify, request
from flask_login import login_required
from ml.predictor import predict_upcoming

predict_bp = Blueprint("predict", __name__)

@predict_bp.route("/predict", methods=["POST"])
@login_required
def predict():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Date JSON lipsa"}), 400
    result = predict_upcoming(
        genres=data.get("genres", "Drama"),
        release_year=data.get("release_year", 2026),
        budget_category=data.get("budget_category", "medium"),
        director_past_avg=data.get("director_past_avg", 3.2),
        franchise=data.get("franchise", False),
        sequel_number=data.get("sequel_number", 1),
    )
    return jsonify(result)
