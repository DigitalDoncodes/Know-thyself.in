#!/bin/bash

# Variables for Teacher 1: Gnanaprakash
EMAIL="gnanaprakash@kclas.ac.in"
PASSWORD="gpsir098"
STUDENT_ID="GP"
NAME="Gnanaprakash"
PHONE="8747978987"

# Go to the script's directory (important for python script to find .env)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Create a Python script to insert or update the user
cat << EOF > create_teacher_temp.py
import os
import datetime
from passlib.hash import bcrypt
from pymongo import MongoClient
import pytz
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/portal")
client = MongoClient(MONGO_URI)
db = client.get_default_database()
if db is None:
    db = client["portal"]

email_var = os.environ.get("TEACHER_EMAIL")
password_var = os.environ.get("TEACHER_PASSWORD")
student_id_var = os.environ.get("TEACHER_STUDENT_ID")
name_var = os.environ.get("TEACHER_NAME")
phone_var = os.environ.get("TEACHER_PHONE")

user = db.users.find_one({"email": email_var})
pw_hash = bcrypt.hash(password_var)

if user:
    db.users.update_one(
        {"email": email_var},
        {"\$set": {
            "pw_hash": pw_hash,
            "role": "teacher",
            "student_id": student_id_var,
            "name": name_var,
            "phone": phone_var,
            "created_at": datetime.datetime.now(pytz.utc)
        }}
    )
    print(f"Updated existing user {email_var} as teacher.")
else:
    db.users.insert_one({
        "email": email_var,
        "pw_hash": pw_hash,
        "role": "teacher",
        "student_id": student_id_var,
        "name": name_var,
        "phone": phone_var,
        "created_at": datetime.datetime.now(pytz.utc)
    })
    print(f"Created new teacher user {email_var}.")

EOF

# Make variables available to the python script's environment
TEACHER_EMAIL="$EMAIL" TEACHER_PASSWORD="$PASSWORD" TEACHER_STUDENT_ID="$STUDENT_ID" TEACHER_NAME="$NAME" TEACHER_PHONE="$PHONE" python create_teacher_temp.py

# Clean up
rm create_teacher_temp.py

echo "Done. You can now login with:"
echo "Email: $EMAIL"
echo "Password: $PASSWORD"