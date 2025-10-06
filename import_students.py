# import_students.py
import os
import csv
import datetime
from pymongo import MongoClient
from dotenv import load_dotenv
from passlib.hash import bcrypt
import pytz

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/portal")
client = MongoClient(MONGO_URI)
db = client.get_default_database()

if db is None:
    db = client["portal"]

CSV_FILE = "students.csv"
DEFAULT_STUDENT_PASSWORD = "password123" # Set a default password for imported students

def import_students_from_csv():
    if not os.path.exists(CSV_FILE):
        print(f"Error: {CSV_FILE} not found in the current directory.")
        return

    imported_count = 0
    skipped_count = 0

    # Define the IST timezone
    IST = pytz.timezone('Asia/Kolkata')

    with open(CSV_FILE, mode='r', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file)
        for row in reader:
            student_id = row.get('student_id', '').strip()
            name = row.get('name', '').strip()
            email = row.get('email', '').strip().lower()
            phone = row.get('phone', '').strip()

            if not (student_id and name and email and phone):
                print(f"Skipping row due to missing data: {row}")
                skipped_count += 1
                continue

            # Check if user already exists by email or student_id
            existing_user = db.users.find_one({
                "$or": [
                    {"email": email},
                    {"student_id": student_id.upper()}
                ]
            })

            if existing_user:
                print(f"User with email '{email}' or student ID '{student_id}' already exists. Skipping.")
                skipped_count += 1
                continue

            # Hash the default password
            pw_hash = bcrypt.hash(DEFAULT_STUDENT_PASSWORD)

            # Get current time in IST, then convert to UTC for storage
            now_ist = datetime.datetime.now(IST)
            now_utc = now_ist.astimezone(pytz.utc).replace(tzinfo=None) # Store as naive UTC

            user_data = {
                "role": "student",
                "student_id": student_id.upper(),
                "name": name,
                "email": email,
                "phone": phone,
                "pw_hash": pw_hash,
                "created_at": now_utc,
            }
            db.users.insert_one(user_data)
            imported_count += 1
            print(f"Imported student: {name} ({student_id})")

    print(f"\n--- Import Summary ---")
    print(f"Successfully imported {imported_count} students.")
    print(f"Skipped {skipped_count} rows (due to missing data or existing users).")
    print(f"Default password for all imported students is: '{DEFAULT_STUDENT_PASSWORD}'")

if __name__ == "__main__":
    import_students_from_csv()