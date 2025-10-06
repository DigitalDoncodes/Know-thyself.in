from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, FileField
from wtforms.validators import DataRequired, Email, Optional, EqualTo
from flask_wtf.file import FileAllowed

class ProfileForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    phone = StringField("Phone", validators=[Optional()])
    password = PasswordField("New Password", validators=[Optional()])
    confirm = PasswordField("Confirm Password", validators=[EqualTo("password", message="Passwords must match")])
    photo = FileField("Profile Picture", validators=[Optional(), FileAllowed(["jpg", "jpeg", "png", "gif"], "Images only!")])