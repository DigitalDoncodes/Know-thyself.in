# schemas.py
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, IntegerField, SubmitField, PasswordField, FileField
from wtforms.validators import DataRequired, Email, Length, Optional, EqualTo, NumberRange
from passlib.hash import bcrypt

# ---------- Forms ----------

class LoginForm(FlaskForm):
    """Login form accepting email or student ID"""
    email_or_sid = StringField("Email or Student ID", validators=[DataRequired()])
    password     = PasswordField("Password", validators=[DataRequired()])
    submit       = SubmitField("Sign In")


class RegisterForm(FlaskForm):
    """Registration form for students"""
    student_id = StringField("Student ID", validators=[DataRequired()])
    name       = StringField("Full Name", validators=[DataRequired()])
    email      = StringField("Email", validators=[Email(), DataRequired()])
    phone      = StringField("Phone", validators=[Length(min=8), DataRequired()])
    password   = PasswordField(
        "Password",
        validators=[Length(min=8), EqualTo("confirm", "Passwords must match")],
    )
    confirm    = PasswordField("Repeat Password")
    submit     = SubmitField("Create Account")


class EditProfileForm(FlaskForm):
    """Form for student profile editing with optional password change"""
    name = StringField("Full Name", validators=[DataRequired()])
    email = StringField("Email", validators=[Email(), DataRequired()])
    phone = StringField("Phone", validators=[Length(min=8), DataRequired()])
    password = PasswordField(
        "New Password", validators=[Optional(), Length(min=8)]
    )
    confirm = PasswordField(
        "Repeat Password",
        validators=[EqualTo("password", "Passwords must match"), Optional()]
    )
    submit = SubmitField("Save Changes")


class JobForm(FlaskForm):
    """Form to create or edit a job"""
    title             = StringField("Job Title", validators=[DataRequired()])
    # ✅ New fields added to the form
    job_description   = TextAreaField("Job Description", validators=[DataRequired()])
    job_specification = TextAreaField("Job Specification", validators=[DataRequired()])
    vacancies         = IntegerField("Vacancies", validators=[DataRequired()])
    pof               = FileField("PoF (PDF)")
    submit            = SubmitField("Save")

# New form for self-assessment
class SelfAssessmentForm(FlaskForm):
    q1 = TextAreaField('How do you approach a new task or a difficult problem? Describe your thought process and initial steps.', validators=[DataRequired()])
    q2 = TextAreaField('What is one skill you have developed recently, and how do you plan to use it in your career?', validators=[DataRequired()])
    q3 = IntegerField('On a scale of 1-10, how confident are you feeling about your resume and interview skills?', validators=[DataRequired(), NumberRange(min=1, max=10)])
    q4 = TextAreaField('What kind of work environment allows you to be most productive and creative?', validators=[DataRequired()])
    q5 = TextAreaField('What is your biggest weakness, and how are you working to overcome it?', validators=[DataRequired()])
    submit = SubmitField('Submit My Reflections')


# ---------- Helper Functions (Password) ----------
def hash_pw(raw):
    """Hash a raw password"""
    return bcrypt.hash(raw)

def check_pw(raw, h):
    """Verify a password against hash"""
    return bcrypt.verify(raw, h)
