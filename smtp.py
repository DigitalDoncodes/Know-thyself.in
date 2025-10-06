# smtp.py
import os
from datetime import datetime, timezone
import pytz
from flask import render_template, url_for, current_app
from flask_mail import Message, Mail
from bson.objectid import ObjectId # Needed for converting app_id if passed as string

# Define the Indian Standard Time zone for local time displays
IST = pytz.timezone("Asia/Kolkata")

# Global mail object (will be initialized by init_mail_app in app.py)
mail = None

def init_mail_app(app_instance):
    """Initializes the Flask-Mail extension with the given app instance."""
    global mail
    mail = Mail(app_instance)
    return mail

def set_mail_instance(mail_instance):
    """Sets the global mail instance for use in this module."""
    global mail
    mail = mail_instance


def send_confirmation_mail(applicant_email, applicant_name, application_id, job_title):
    """Send confirmation email to the student."""
    if not mail:
        print("Mail instance not initialized in smtp.py (send_confirmation_mail)")
        return

    try:
        with current_app.app_context():
            now = datetime.now(IST)
            sender_email = current_app.config.get("MAIL_USERNAME")

            msg = Message(
                subject="✅ Application Files Received – Next Step: Review",
                sender=sender_email,
                recipients=[applicant_email],
            )

            msg.html = render_template(
                "confirmation_mail.html",
                name=applicant_name,
                job_title=job_title,
                application_id=application_id,
                submitted_date=now.strftime("%B %d, %Y – %I:%M %p IST")
            )
            mail.send(msg)
    except Exception as e:
        print(f"❌ Error sending confirmation email: {e}")

def send_otp_email(to_email, otp):
    """Send OTP email for password change verification"""
    if not mail:
        print("Mail instance not initialized in smtp.py (send_otp_email)")
        return
    
    try:
        with current_app.app_context():
            sender_email = current_app.config.get("MAIL_USERNAME")
            msg = Message(
                subject='🔑 Your OTP for Password Change Verification',
                sender=sender_email,
                recipients=[to_email]
            )
            msg.body = f"Your One-Time Password (OTP) to change your account password is: {otp}\n\nThis code expires soon. If you did not request this change, please ignore this email."
            mail.send(msg)
    except Exception as e:
        print(f"❌ Error sending OTP email: {e}")

def send_resume_and_photo_mail(resume_filename, photo_filename, applicant_email, job_title):
    """Sends student's resume and photo as attachments to the admin for review."""
    if not mail:
        print("Mail instance not initialized in smtp.py (send_resume_and_photo_mail)")
        return
    
    try:
        with current_app.app_context():
            admin_recipient = os.getenv("NOTICE_MAILBOX", "admin@example.com")
            sender_email = current_app.config.get("MAIL_USERNAME")
            
            msg = Message(
                subject=f"📥 NEW SUBMISSION: '{job_title}' from {applicant_email}",
                sender=sender_email,
                recipients=[admin_recipient]
            )
            msg.body = (
                f"Student {applicant_email} ({os.path.splitext(resume_filename)[0]}) has successfully uploaded a résumé and photo for the job '{job_title}'.\n\nPlease review the attached files."
            )

            # Use standard os.path.join for reliable path access to the UPLOAD_FOLDER
            upload_dir = current_app.config.get("UPLOAD_FOLDER", "uploads")
            resume_path = os.path.join(upload_dir, resume_filename)
            photo_path = os.path.join(upload_dir, photo_filename)
            
            # --- Resume Attachment ---
            if os.path.exists(resume_path):
                with open(resume_path, 'rb') as rf:
                    mime_type = 'application/pdf' if resume_filename.lower().endswith('.pdf') else 'application/octet-stream'
                    msg.attach(resume_filename, mime_type, rf.read())
            else:
                print(f"Warning: Resume file not found at {resume_path}")

            # --- Photo Attachment ---
            if os.path.exists(photo_path):
                with open(photo_path, 'rb') as pf:
                    mime_type = 'image/jpeg' if photo_filename.lower().endswith(('.jpg', '.jpeg')) else 'image/png' if photo_filename.lower().endswith('.png') else 'application/octet-stream'
                    msg.attach(photo_filename, mime_type, pf.read())
            else:
                print(f"Warning: Photo file not found at {photo_path}")
            
            mail.send(msg)
    except Exception as e:
        print(f"❌ Error sending resume/photo email: {e}")

def send_admin_notification(student_name, job_title, student_email):
    """Sends a notification to the admin about a new application (less detailed than the one with attachments)."""
    if not mail:
        print("Mail instance not initialized in smtp.py (send_admin_notification)")
        return
    
    try:
        with current_app.app_context():
            admin_recipient = os.getenv("NOTICE_MAILBOX", "admin@example.com")
            sender_email = current_app.config.get("MAIL_USERNAME")
            
            msg = Message(
                subject=f"🔔 New Application Alert: {job_title}",
                sender=sender_email,
                recipients=[admin_recipient]
            )
            msg.body = f"""A new job application has been submitted and files uploaded.

Student Name: {student_name}
Student Email: {student_email}
Job Title: {job_title}
Submitted At: {datetime.now(IST).strftime('%d %b %Y, %I:%M %p IST')}

Check your secure email or the admin panel to review the documents.
"""
            mail.send(msg)
    except Exception as e:
        print(f"❌ Error sending admin notification email: {e}")

def send_application_status_email(student_email, student_name, status, job_title, feedback=None, application_id=None):
    """
    Sends application status updates (approved, rejected, corrections_needed) to students.
    Includes logic for generating a direct correction link.
    """
    if not mail:
        print("Mail instance not initialized in smtp.py (send_application_status_email)")
        return

    templates = {
        "approved": ("email_templates/approved_status.html", f"🎉 Application Approved for {job_title}!"),
        "rejected": ("email_templates/rejected_status.html", f"Update on your application for {job_title}"),
        "rejected_auto": ("email_templates/rejected_status.html", f"Update on your application for {job_title}"),
        "needs_corrections": ("email_templates/corrections_status.html", f"✍️ Corrections Needed for Your Application"),
    }

    if status not in templates:
        print(f"[✘] Unknown status: {status} in send_application_status_email. Exiting.")
        return

    template_name, subject = templates[status]
    
    try:
        with current_app.app_context():
            sender_email = current_app.config.get("MAIL_USERNAME")

            # Generate links dynamically
            portal_link = url_for('student_dashboard', _external=True)
            
            # CRITICAL FIX: Generate direct link for corrections if status is 'needs_corrections'
            correction_link = None
            if status == "needs_corrections" and application_id:
                # Assuming 'correction_portal' is the new route we agreed to create
                correction_link = url_for('correction_portal', app_id=application_id, _external=True)

            html_body = render_template(
                template_name,
                student_name=student_name,
                job_title=job_title,
                feedback=feedback,
                portal_link=portal_link,
                correction_link=correction_link, # Pass the new correction link
                current_year=datetime.now().year
            )

            msg = Message(
                subject=subject, 
                sender=sender_email,
                recipients=[student_email], 
                html=html_body
            )
            mail.send(msg)
    
        print(f"[✓] Email sent to {student_email} – {status}")
    except Exception as e:
        print(f"[✘] Error sending email: {e}")