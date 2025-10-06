#!/bin/bash

# Variables
EMAIL="gnanaprakash@kclas.ac.in"
PASSWORD="gpsir098"
STUDENT_ID="GP"
NAME="Gnanaprakash"
PHONE="8747978987"   # dummy phone number

# Activate your virtual environment (adjust path if needed)
source ../jobportal_env/bin/activate

# Create a Python script to insert or update the user
cat << EOF > create_teacher.py
import os
import datetime
from passlib.hash import bcrypt
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/portal")
client = MongoClient(MONGO_URI)
db = client.get_default_database()
if db is None:
    db = client["portal"]

# Check if user exists
user = db.users.find_one({"email": "$EMAIL"})
pw_hash = bcrypt.hash("$PASSWORD")

if user:
    # Update password and role
    db.users.update_one(
        {"email": "$EMAIL"},
        {"\$set": {
            "pw_hash": pw_hash,
            "role": "teacher",
            "student_id": "$STUDENT_ID",
            "name": "$NAME",
            "phone": "$PHONE",
            "created_at": datetime.datetime.now(datetime.timezone.utc)
        }}
    )
    print(f"Updated existing user {EMAIL} as teacher.")
else:
    # Insert new user as teacher
    db.users.insert_one({
        "email": "$EMAIL",
        "pw_hash": pw_hash,
        "role": "teacher",
        "student_id": "$STUDENT_ID",
        "name": "$NAME",
        "phone": "$PHONE",
        "created_at": datetime.datetime.now(datetime.timezone.utc)
    })
    print(f"Created new teacher user {EMAIL}.")

EOF

# Run the Python script
python create_teacher.py

# Clean up
rm create_teacher.py

echo "Done. You can now login with:"
echo "Email: $EMAIL"
echo "Password: $PASSWORD"
