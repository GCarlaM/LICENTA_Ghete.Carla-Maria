from flask import Flask, render_template
from dotenv import load_dotenv
import os

from extensions import db, login_manager, bcrypt

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-key-schimba-in-productie")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///cinematch.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
login_manager.init_app(app)
bcrypt.init_app(app)

login_manager.login_view = "auth.login"
login_manager.login_message = "Trebuie sa fii autentificat."

from routes.movies import movies_bp
from routes.auth import auth_bp
from routes.recommend import recommend_bp
from routes.predict import predict_bp
from routes.dashboard import dashboard_bp
from routes.upcoming import upcoming_bp
from routes.profile import profile_bp

app.register_blueprint(movies_bp)
app.register_blueprint(auth_bp, url_prefix="/auth")
app.register_blueprint(recommend_bp, url_prefix="/api")
app.register_blueprint(predict_bp, url_prefix="/api")
app.register_blueprint(dashboard_bp)
app.register_blueprint(upcoming_bp)
app.register_blueprint(profile_bp)

@app.route("/recommendations")
def recommendations_page():
    return render_template("recommend.html")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)