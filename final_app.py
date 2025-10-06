# app.py
import os
import io
import random
import base64
from datetime import datetime, timedelta, timezone
from dateutil import tz
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for, flash, abort, session, send_file
)
from werkzeug.utils import secure_filename
from bson.objectid import ObjectId
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# --- CONFIG ---
APP_SECRET = os.getenv("APP_SECRET", "dev-secret-change-me")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/know_thyself")
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
ALLOWED_RESUME = {"pdf", "doc", "docx"}
ALLOWED_PHOTO = {"png", "jpg", "jpeg"}
BREVO_API_KEY = os.getenv("BREVO_API_KEY")  # your Brevo API key
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")
IST = tz.gettz("Asia/Kolkata")  # India timezone

# create upload folder
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Flask + Mongo + Login-like helpers ---
from pymongo import MongoClient
client = MongoClient(MONGO_URI)
db = client.get_default_database()

from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin

app = Flask(__name__)
app.secret_key = APP_SECRET
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

login_manager = LoginManager(app)
login_manager.login_view = "login"

# --- Brevo setup ---
try:
    import sib_api_v3_sdk
    from sib_api_v3_sdk.rest import ApiException
    sib_config = sib_api_v3_sdk.Configuration()
    sib_config.api_key['api-key'] = BREVO_API_KEY
    sib_api_client = sib_api_v3_sdk.ApiClient(sib_config)
    transactional_api = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_client)
except Exception as e:
    transactional_api = None
    print("Brevo SDK not available or API key missing:", e)

# --- Cloudinary setup (optional) ---
try:
    import cloudinary
    import cloudinary.uploader
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET
    )
except Exception:
    cloudinary = None

# --- Simple User class for flask-login backed by MongoDB ---
class User(UserMixin):
    def __init__(self, user_doc):
        self._doc = user_doc

    @property
    def id(self):
        # flask-login expects a string id
        return str(self._doc.get("_id"))

    @property
    def role(self):
        return self._doc.get("role", "student")

    @property
    def name(self):
        return self._doc.get("name", "")

    @property
    def email(self):
        return self._doc.get("email", "")

    def get(self, key, default=None):
        return self._doc.get(key, default)

@login_manager.user_loader
def load_user(user_id):
    u = db.users.find_one({"_id": ObjectId(user_id)})
    if not u:
        return None
    return User(u)

# --- Utility functions ---
def allowed_file(filename, allowed_set):
    if not filename:
        return False
    ext = filename.rsplit('.', 1)[-1].lower()
    return ext in allowed_set

def now_ist():
    """Return timezone-aware current time in IST."""
    return datetime.now(timezone.utc).astimezone(IST)

def to_utc(dt):
    """Convert timezone-aware dt to UTC (naive or aware accepted)."""
    if dt.tzinfo is None:
        # assume IST if local naive? we standardize clients to IST in this app
        return dt.replace(tzinfo=IST).astimezone(timezone.utc)
    return dt.astimezone(timezone.utc)

def ensure_collections():
    # Create indexes or initial data if required (called at startup)
    db.users.create_index("email", unique=True)
    db.jobs.create_index("title")
    db.applications.create_index("applicant_id")
    db.growth_hub.create_index("user_id")
    db.self_assessments.create_index("user_id")
    db.otp_store.create_index("user_id")
ensure_collections()

# Role decorator
def teacher_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "teacher":
            abort(403)
        return f(*args, **kwargs)
    return decorated

# --- Email helpers using Brevo transactional API ---
def send_brevo_email(to_email, to_name, subject, html_content, attachments=None, sender_email="psychologyresumemail@gmail.com", sender_name="Know-thyself"):
    """
    Send an email via Brevo (SendSmtpEmail model).
    attachments: list of tuples [(filename, bytes_data, mime_type), ...]
    """
    if transactional_api is None:
        app.logger.warning("Brevo transactional API is not configured. Email not sent.")
        return False

    to_obj = [{"email": to_email, "name": to_name}]
    sender_obj = {"email": sender_email, "name": sender_name}

    smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=to_obj,
        sender=sender_obj,
        subject=subject,
        html_content=html_content
    )

    # Attach files if provided
    if attachments:
        # Each attachment is expected as (filename, bytes, mime)
        att_list = []
        for fname, bdata, mime in attachments:
            b64 = base64.b64encode(bdata).decode("utf-8")
            att_list.append({"name": fname, "content": b64})
        smtp_email.attachment = att_list

    try:
        transactional_api.send_transac_email(smtp_email)
        app.logger.info("Email sent to %s", to_email)
        return True
    except ApiException as e:
        app.logger.exception("Brevo API exception: %s", e)
        return False

# --- Status email wrapper using templates in templates/ ---
def send_status_email_brevo(student_email, student_name, job_title, status, feedback=None, attachments=None, extra_ctx=None):
    """
    status: one of 'approved', 'rejected', 'corrections_needed', 'submitted', 'resubmitted'
    attachments: list of (filename, bytes, mime) to attach
    extra_ctx: dict of extra template context
    """
    template_map = {
        "approved": "approved_status.html",
        "rejected": "rejected_status.html",
        "corrections_needed": "corrections_status.html",
        "submitted": "submitted_status.html",
        "resubmitted": "resubmitted_status.html",
        "reupload": "reupload_status.html"
    }
    tmpl = template_map.get(status)
    if not tmpl:
        app.logger.warning("No email template for status %s", status)
        return False

    ctx = {
        "student_name": student_name,
        "job_title": job_title,
        "feedback": feedback or "",
        "portal_link": url_for("login", _external=True),
        "current_year": now_ist().year
    }
    if extra_ctx:
        ctx.update(extra_ctx)

    html_body = render_template(tmpl, **ctx)
    subject = f"Application update for {job_title}: {status.replace('_',' ').title()}"
    return send_brevo_email(student_email, student_name, subject, html_body, attachments=attachments)

# --- Authentication routes (simple email/password) ---
from werkzeug.security import generate_password_hash, check_password_hash

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        role = request.form.get("role", "student")
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        if not all([name, email, password]):
            flash("Please fill all required fields", "warning")
            return redirect(url_for("register"))

        if db.users.find_one({"email": email}):
            flash("Email already registered", "warning")
            return redirect(url_for("register"))

        user_doc = {
            "name": name,
            "email": email,
            "password_hash": generate_password_hash(password),
            "role": role,
            "photo_url": None,
            "created_at": now_ist()
        }
        result = db.users.insert_one(user_doc)
        flash("Account created. Please log in.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    # This route expects your existing login template to show the form; we keep signature minimal.
    from flask import g
    if request.method == "POST":
        identifier = request.form.get("identifier")  # email or student id
        password = request.form.get("password")
        # if identifier is an ObjectId string, try find by _id
        user_doc = None
        try:
            if ObjectId.is_valid(identifier):
                user_doc = db.users.find_one({"_id": ObjectId(identifier)})
        except Exception:
            user_doc = None

        if not user_doc:
            user_doc = db.users.find_one({"email": identifier.lower()})

        if not user_doc:
            flash("Invalid credentials", "danger")
            return redirect(url_for("login"))

        if not check_password_hash(user_doc.get("password_hash", ""), password):
            flash("Invalid credentials", "danger")
            return redirect(url_for("login"))

        user = User(user_doc)
        login_user(user)

        # If user has a pending application that requires upload, direct them to upload page first
        pending_app = db.applications.find_one({
            "applicant_id": ObjectId(user.id),
            "status": {"$in": ["pending_upload", "corrections_needed"]}
        })
        if pending_app:
            return redirect(url_for("upload_files", app_id=str(pending_app["_id"])))

        # otherwise to dashboard
        if user.role == "teacher":
            return redirect(url_for("teacher_dashboard"))
        return redirect(url_for("student_dashboard"))
    # GET
    return render_template("login.html")

@app.route("/logout")
def logout():
    logout_user()
    flash("Logged out", "info")
    return redirect(url_for("login"))

# --- Student dashboard & apply flow ---
@app.route("/student/")
@login_required
def student_dashboard():
    if current_user.role != "student":
        abort(403)
    # show jobs and applications
    jobs = list(db.jobs.find({}))
    apps = list(db.applications.find({"applicant_id": ObjectId(current_user.id)}))
    # attach job titles and compute deadlines
    for a in apps:
        j = db.jobs.find_one({"_id": a.get("job_id")})
        a["job_title"] = j.get("title") if j else "Unknown Job"
        if a.get("deadline"):
            # store ms timestamp for JS if needed
            a["deadline_ts"] = int(a["deadline"].timestamp() * 1000) if isinstance(a["deadline"], datetime) else None
    # hide apply buttons if student already has an active application (pending_upload/submitted/resubmitted)
    active = db.applications.find_one({"applicant_id": ObjectId(current_user.id), "status": {"$in": ["pending_upload", "submitted", "resubmitted", "approved"]}})
    return render_template("student_dashboard.html", jobs=jobs, applications=apps, has_active=bool(active))

@app.route("/apply/<job_id>", methods=["POST"])
@login_required
def apply_job(job_id):
    if current_user.role != "student":
        abort(403)
    # check if student already applied to any job (policy: one student one job)
    existing = db.applications.find_one({"applicant_id": ObjectId(current_user.id), "status": {"$in": ["pending_upload", "submitted", "resubmitted", "approved"]}})
    if existing:
        flash("You already have an active application. You cannot apply to another job.", "warning")
        return redirect(url_for("student_dashboard"))

    job = db.jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        flash("Job not found", "danger")
        return redirect(url_for("student_dashboard"))

    # create application document with deadline 48 hours from now (IST)
    application_time = now_ist()
    deadline = application_time + timedelta(hours=48)
    app_doc = {
        "job_id": job["_id"],
        "applicant_id": ObjectId(current_user.id),
        "job_title": job.get("title"),
        "status": "pending_upload",
        "application_time": application_time,
        "deadline": deadline,
        "created_at": application_time
    }
    result = db.applications.insert_one(app_doc)
    flash("Application created. Please upload your resume and photo.", "info")
    return redirect(url_for("upload_files", app_id=str(result.inserted_id)))

# --- Upload files route (force-upload flow) ---
@app.route("/upload/<app_id>", methods=["GET", "POST"])
@login_required
def upload_files(app_id):
    application = db.applications.find_one({"_id": ObjectId(app_id)})
    if not application:
        abort(404)
    if str(application.get("applicant_id")) != current_user.id:
        abort(403)

    # Block expired or rejected
    app_deadline = application.get("deadline")
    if app_deadline:
        # Ensure both sides are timezone-aware
        # Convert stored deadline to timezone-aware if naive by assuming it's IST (our design)
        if app_deadline.tzinfo is None:
            app_deadline = app_deadline.replace(tzinfo=IST)
        if now_ist() > app_deadline:
            db.applications.update_one({"_id": application["_id"]}, {"$set": {"status": "expired"}})
            flash("Upload deadline expired (48 hours).", "danger")
            return render_template("upload_blocked.html", app=application)

    if application.get("status") in ["expired", "rejected"]:
        flash("This application is expired/rejected. Upload not allowed.", "danger")
        return render_template("upload_blocked.html", app=application)

    if request.method == "POST":
        resume = request.files.get("resume")
        photo = request.files.get("photo")
        updates = {}
        attachments = []

        if resume and allowed_file(resume.filename, ALLOWED_RESUME):
            rext = resume.filename.rsplit('.', 1)[1].lower()
            resume_name = secure_filename(f"{app_id}_resume.{rext}")
            resume_path = os.path.join(app.config["UPLOAD_FOLDER"], resume_name)
            resume.save(resume_path)
            updates["resume_filename"] = resume_name
            updates["resume_upload_time"] = now_ist()
            # prepare attachment bytes for teacher email
            with open(resume_path, "rb") as fh:
                attachments.append((resume_name, fh.read(), "application/octet-stream"))

        if photo and allowed_file(photo.filename, ALLOWED_PHOTO):
            pext = photo.filename.rsplit('.', 1)[1].lower()
            photo_name = secure_filename(f"{app_id}_photo.{pext}")
            photo_path = os.path.join(app.config["UPLOAD_FOLDER"], photo_name)
            photo.save(photo_path)
            updates["photo_filename"] = photo_name
            # prepare attachment bytes
            with open(photo_path, "rb") as fh:
                attachments.append((photo_name, fh.read(), "image/jpeg"))

        if updates:
            updates["status"] = "submitted"
            updates["last_updated"] = now_ist()
            db.applications.update_one({"_id": ObjectId(app_id)}, {"$set": updates})

            # send confirmation email to student
            student = db.users.find_one({"_id": application["applicant_id"]})
            student_name = student.get("name", "Student") if student else "Student"
            job_title = application.get("job_title", "Student Submission")

            send_status_email_brevo(
                student_email=student.get("email"),
                student_name=student_name,
                job_title=job_title,
                status="submitted",
                attachments=None  # student's confirmation need not attach files
            )

            # send teacher notification with attachments (teacher inbox address configurable)
            teacher_inbox = os.getenv("TEACHER_INBOX", "psychologyresumemail@gmail.com")
            teacher_name = "Psychology Admin"
            # email body: render a template 'teacher_upload_notification.html' with context
            html_body = render_template("teacher_upload_notification.html",
                                       student_name=student_name,
                                       student_email=student.get("email"),
                                       job_title=job_title,
                                       upload_time=now_ist().strftime("%d %b %Y %I:%M %p"))
            send_brevo_email(teacher_inbox, teacher_name, f"New Upload - {job_title}", html_body, attachments=attachments)

            flash("Files uploaded successfully! Confirmation has been emailed.", "success")
            return redirect(url_for("student_dashboard"))
        else:
            flash("No files uploaded or invalid file types.", "warning")
            return redirect(url_for("upload_files", app_id=app_id))

    # GET
    return render_template("upload_files.html", app=application)

# --- Teacher Dashboard & assess students ---
@app.route("/teacher/")
@login_required
@teacher_required
def teacher_dashboard():
    # teacher summary: total applications by status, quick links
    total = db.applications.count_documents({})
    pending = db.applications.count_documents({"status": "pending_upload"})
    submitted = db.applications.count_documents({"status": "submitted"})
    corrections = db.applications.count_documents({"status": "corrections_needed"})
    approved = db.applications.count_documents({"status": "approved"})
    return render_template("teacher_dashboard.html", total=total, pending=pending, submitted=submitted, corrections=corrections, approved=approved)

@app.route("/teacher/students", methods=["GET", "POST"])
@app.route("/teacher/students/<job_id>", methods=["GET", "POST"])
@login_required
@teacher_required
def assess_students(job_id=None):
    # POST updates
    if request.method == "POST":
        app_id = request.form.get("app_id")
        status = request.form.get("status")
        feedback = request.form.get("feedback", "").strip()
        if not app_id:
            flash("Missing application ID", "danger")
            return redirect(url_for("assess_students"))

        application = db.applications.find_one({"_id": ObjectId(app_id)})
        if not application:
            flash("Application not found", "danger")
            return redirect(url_for("assess_students"))

        db.applications.update_one({"_id": application["_id"]}, {"$set": {
            "status": status,
            "teacher_feedback": feedback,
            "last_updated": now_ist()
        }})

        # Send email to student about status
        student = db.users.find_one({"_id": application["applicant_id"]})
        student_email = student.get("email") if student else None
        student_name = student.get("name") if student else "Student"
        job_title = application.get("job_title", "Your Applied Job")

        # If corrections needed, instruct student to reupload -> set status to corrections_needed
        if status == "corrections_needed":
            send_status_email_brevo(student_email, student_name, job_title, "corrections_needed", feedback=feedback)
        elif status == "approved":
            send_status_email_brevo(student_email, student_name, job_title, "approved", feedback=feedback)
        elif status == "rejected":
            send_status_email_brevo(student_email, student_name, job_title, "rejected", feedback=feedback)
        elif status == "resubmitted":
            send_status_email_brevo(student_email, student_name, job_title, "resubmitted", feedback=feedback)

        flash("Application updated and student notified.", "success")
        return redirect(url_for("assess_students", job_id=job_id) if job_id else url_for("assess_students"))

    # GET filters
    name_filter = request.args.get("name", "").strip()
    status_filter = request.args.get("status", "").strip()
    resume_filter = request.args.get("resume", "").strip()

    query = {}
    if job_id:
        query["job_id"] = ObjectId(job_id)
    if status_filter:
        query["status"] = status_filter
    if resume_filter == "uploaded":
        query["resume_filename"] = {"$ne": None}
    elif resume_filter == "not_uploaded":
        query["resume_filename"] = None

    applications = list(db.applications.find(query).sort("created_at", -1))
    # Attach user + job info
    for a in applications:
        user = db.users.find_one({"_id": a.get("applicant_id")})
        job = db.jobs.find_one({"_id": a.get("job_id")})
        a["user"] = {"name": user.get("name") if user else "Unknown", "email": user.get("email") if user else "N/A"}
        a["job"] = {"title": job.get("title") if job else "Unknown Job"}
        # upload duration hours
        if a.get("resume_upload_time") and a.get("application_time"):
            delta = a["resume_upload_time"] - a["application_time"]
            a["upload_duration_hours"] = round(delta.total_seconds() / 3600, 1)
        else:
            a["upload_duration_hours"] = None

    statuses = ["pending_upload", "submitted", "corrections_needed", "approved", "rejected", "resubmitted"]
    resume_options = [{"value": "", "label": "All"}, {"value": "uploaded", "label": "Uploaded"}, {"value": "not_uploaded", "label": "Not uploaded"}]
    return render_template("assess_students.html", applications=applications, statuses=statuses, resume_options=resume_options, name_filter=name_filter, status_filter=status_filter, resume_filter=resume_filter)

# --- Utility endpoints for serving uploaded files (teacher only) ---
@app.route("/uploads/<filename>")
@login_required
def serve_upload(filename):
    # restrict access: teachers can view any; students only their own
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if not os.path.exists(path):
        abort(404)
    # simple permission enforcement
    if current_user.role == "student":
        # ensure the filename belongs to one of their applications
        app_doc = db.applications.find_one({"applicant_id": ObjectId(current_user.id), "$or": [{"resume_filename": filename}, {"photo_filename": filename}]})
        if not app_doc:
            abort(403)
    return send_file(path, as_attachment=True)

# --- Profile edit with OTP verification & Cloudinary upload ---
@app.route("/edit-profile", methods=["GET", "POST"])
@login_required
def edit_profile():
    if request.method == "POST":
        name = request.form.get("name", current_user.name)
        email = request.form.get("email", current_user.email)
        phone = request.form.get("phone", "")
        password = request.form.get("password", "")
        photo_file = request.files.get("photo")

        pending_data = {"name": name, "email": email, "phone": phone}
        if password:
            pending_data["password_hash"] = generate_password_hash(password)

        if photo_file and cloudinary:
            # upload to Cloudinary
            upload_result = cloudinary.uploader.upload(photo_file,
                                                      folder="know_thyself/profiles",
                                                      public_id=f"{current_user.id}_profile",
                                                      overwrite=True,
                                                      transformation=[{"width": 400, "height": 400, "crop": "fill"}])
            pending_data["photo_url"] = upload_result.get("secure_url")

        # generate OTP and save to otp_store collection with expiry 5 minutes
        otp_code = f"{random.randint(100000, 999999)}"
        db.otp_store.update_one({"user_id": ObjectId(current_user.id)}, {"$set": {
            "otp": otp_code,
            "pending_data": pending_data,
            "expires_at": (now_ist() + timedelta(minutes=5))
        }}, upsert=True)

        # send OTP email via Brevo
        html = render_template("otp_email.html", otp=otp_code, user_name=current_user.name)
        send_brevo_email(current_user.email, current_user.name, "Your OTP to confirm profile change", html)

        flash("OTP sent to your email. Please verify to apply changes.", "info")
        return redirect(url_for("verify_otp"))

    # GET
    user_doc = db.users.find_one({"_id": ObjectId(current_user.id)})
    return render_template("edit_profile.html", user=user_doc)

@app.route("/verify-otp", methods=["GET", "POST"])
@login_required
def verify_otp():
    record = db.otp_store.find_one({"user_id": ObjectId(current_user.id)})
    if not record:
        flash("No pending changes found.", "warning")
        return redirect(url_for("edit_profile"))

    if request.method == "POST":
        otp = request.form.get("otp", "").strip()
        if otp == record.get("otp") and now_ist() <= record.get("expires_at"):
            # apply pending_data to users collection
            pd = record.get("pending_data", {})
            if pd.get("password_hash"):
                # already hashed
                pass
            db.users.update_one({"_id": ObjectId(current_user.id)}, {"$set": pd})
            db.otp_store.delete_one({"user_id": ObjectId(current_user.id)})
            flash("Profile updated successfully.", "success")
            return redirect(url_for("student_dashboard") if current_user.role == "student" else url_for("teacher_dashboard"))
        else:
            flash("Invalid or expired OTP.", "danger")
            return redirect(url_for("verify_otp"))
    return render_template("verify_otp.html")

# --- Misc routes for adding jobs (teacher) and growth hub/self assessment basics ---
@app.route("/teacher/create-job", methods=["GET", "POST"])
@login_required
@teacher_required
def create_job():
    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        vacancies = int(request.form.get("vacancies", 1))
        db.jobs.insert_one({"title": title, "description": description, "vacancies": vacancies, "created_at": now_ist()})
        flash("Job created", "success")
        return redirect(url_for("teacher_dashboard"))
    return render_template("create_job.html")

# Minimal growth hub / self assessment endpoints (expand to match templates)
@app.route("/growth-hub", methods=["GET", "POST"])
@login_required
def growth_hub():
    if request.method == "POST":
        payload = request.form.to_dict()
        payload["user_id"] = ObjectId(current_user.id)
        payload["created_at"] = now_ist()
        db.growth_hub.insert_one(payload)
        flash("Saved to Growth Hub", "success")
        return redirect(url_for("growth_hub"))
    entries = list(db.growth_hub.find({"user_id": ObjectId(current_user.id)}).sort("created_at", -1))
    return render_template("growth_hub.html", entries=entries)

@app.route("/self-assessment", methods=["GET", "POST"])
@login_required
def self_assessment():
    if request.method == "POST":
        answers = request.form.to_dict()
        ans_doc = {"user_id": ObjectId(current_user.id), "answers": answers, "created_at": now_ist()}
        db.self_assessments.insert_one(ans_doc)
        flash("Self assessment saved", "success")
        return redirect(url_for("self_assessment"))
    last = db.self_assessments.find_one({"user_id": ObjectId(current_user.id)}, sort=[("created_at", -1)])
    return render_template("self_assessment.html", last=last)

# --- Error handlers ---
@app.errorhandler(403)
def forbidden(e):
    return render_template("403.html"), 403

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

# --- Run app (local development) ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)