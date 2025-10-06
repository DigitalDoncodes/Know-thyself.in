# db.py
import os
from flask_pymongo import PyMongo
from flask_mail import Mail
from apscheduler.schedulers.background import BackgroundScheduler
from flask_login import LoginManager, UserMixin
import pytz
from flask import Flask
from bson.objectid import ObjectId
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env

mongo = PyMongo()
mail = Mail()
login_manager = LoginManager()
scheduler = BackgroundScheduler()

# Define timezone for consistent date/time handling
IST = pytz.timezone('Asia/Kolkata')

# ---------- User Model ----------
class User(UserMixin):
    """User class wrapping MongoDB user document for Flask-Login"""

    def __init__(self, doc):
        self.id = str(doc["_id"])
        self.role = doc["role"]
        self.email = doc["email"]
        self.student_id = doc.get("student_id")
        self.name = doc["name"]

    @staticmethod
    def get_user_by_id(user_id):
        """Load user by MongoDB ObjectId string"""
        doc = mongo.db.users.find_one({"_id": ObjectId(user_id)})
        return User(doc) if doc else None

def init_extensions(app: Flask):
    """
    Initializes Flask extensions with the given Flask app object.
    """
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "a_very_secret_key_that_should_be_changed"),
        MONGO_URI=os.getenv("MONGO_URI"),
        UPLOAD_FOLDER=os.getenv("UPLOAD_FOLDER", "uploads"),
        MAX_CONTENT_LENGTH=int(os.getenv("MAX_CONTENT_LENGTH", 5 * 1024 * 1024)),
        MAIL_SERVER=os.getenv("MAIL_SERVER", "smtp.gmail.com"),
        MAIL_PORT=int(os.getenv("MAIL_PORT", 465)),
        MAIL_USE_TLS=os.getenv("MAIL_USE_TLS", "false").lower() == "true",
        MAIL_USE_SSL=os.getenv("MAIL_USE_SSL", "true").lower() == "true",
        MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
        MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    )

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    mongo.init_app(app)
    mail.init_app(app)
    login_manager.init_app(app)
    
    login_manager.login_view = "login"
    login_manager.user_loader(User.get_user_by_id)
    
    if not scheduler.running:
        scheduler.start()