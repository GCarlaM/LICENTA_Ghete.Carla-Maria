from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from ml.recommender import get_recommendations

recommend_bp = Blueprint("recommend", __name__)

@recommend_bp.route("/recommendations")
@login_required
def recommendations():
    recs = get_recommendations(user_id=current_user.id, n=10)
    return jsonify({"user_id": current_user.id, "recommendations": recs})
