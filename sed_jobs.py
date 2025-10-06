import os
import datetime
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
import pytz

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/portal")
client = MongoClient(MONGO_URI)
db = client.get_default_database()

if db is None:
    db = client["portal"]

# *** STEP 1: Find your teacher's ObjectId first (if you haven't already) ***
# You can run `python find-teacher.py` or uncomment this function to see teachers in DB.
def find_teacher_id_in_script():
    print("Finding teachers in the database:")
    print("=" * 50)
    teachers = db.users.find({"role": "teacher"})
    for teacher in teachers:
        print(f"Name: {teacher.get('name', 'N/A')}")
        print(f"Email: {teacher.get('email', 'N/A')}")
        print(f"ObjectId: {teacher['_id']}")
        print("-" * 30)

# Uncomment the line below to see teachers if needed, then re-comment before full run.
# find_teacher_id_in_script()

# *** STEP 2: Replace this with your actual teacher's ObjectId ***
# You MUST run `python find-teacher.py` (or the internal find_teacher_id_in_script) first,
# copy the ObjectId string, and paste it here.
TEACHER_USER_ID = "650b2b8c3d4a0f1e2c3b4a5d"
def clear_and_import_jobs():
    try:
        teacher_obj_id = ObjectId(TEACHER_USER_ID)
    except Exception:
        print(f"Error: Invalid TEACHER_USER_ID format: '{TEACHER_USER_ID}'. Please copy the full ObjectId string including quotes.")
        return 0

    deleted_count = db.jobs.delete_many({"created_by": teacher_obj_id}).deleted_count
    print(f"Deleted {deleted_count} existing jobs for teacher {TEACHER_USER_ID}")
    
    jobs = [
        {"title": "Scientist B, DIPR, DRDO", "description": "Research position at the Defence Institute of Psychological Research, DRDO.", "vacancies": 1},
        {"title": "Assistant Professor, State Govt University", "description": "Teaching psychology and conducting research at a state government university.", "vacancies": 2},
        {"title": "Manager, L & D, A manufacturing company", "description": "Manage learning and development activities for employees in a manufacturing company.", "vacancies": 1},
        {"title": "Clinical Psychologist", "description": "Specialist in learning difficulties and ADHD interventions.", "vacancies": 1},
        {"title": "Course Developer / Instructional Designer", "description": "Develop online psychology courses for platforms suchs as SWAYAM, NPTEL, or Coursera.", "vacancies": 1},
        {"title": "Program Manager – Mental Health (NGOs)", "description": "Manage field research and outreach programs for NGOs like Sangath or The Live Love Laugh Foundation.", "vacancies": 1},
        {"title": "Mental Health Coach / Digital Therapist", "description": "Provide digital therapy or coaching on platforms such as MindPeers, YourDOST, or BetterLYF.", "vacancies": 2},
        {"title": "Youth Program Officer – UNESCO, Pratham", "description": "Coordinate adolescent well-being and life skills programs.", "vacancies": 1},
        {"title": "AI Ethics Consultant", "description": "Work on human behavior and AI alignment for organizations like Google DeepMind or Microsoft Research.", "vacancies": 1},
        {"title": "Performance Coach – Sports & High-Pressure Professions", "description": "Support athletes, musicians, or students in high-pressure environments.", "vacancies": 1},
    ]
    
    now_utc = datetime.datetime.now(pytz.utc)
    inserted_jobs = []
    
    for job in jobs:
        job["status"] = "open"
        job["created_at"] = now_utc
        job["created_by"] = teacher_obj_id
        
        result = db.jobs.insert_one(job)
        inserted_jobs.append(result.inserted_id)
    
    print(f"Successfully inserted {len(inserted_jobs)} jobs with proper created_by field")
    return len(inserted_jobs)

# *** STEP 3: Run the import (only after setting 'TEACHER_USER_ID') ***
if __name__ == "__main__":
    if TEACHER_USER_ID == "PASTE_YOUR_TEACHER_OBJECTID_HERE":
        print("!!!! IMPORTANT: Please update TEACHER_USER_ID in sed_jobs.py with your actual teacher's ObjectId. !!!!")
        print("Run `python find-teacher.py` to get your teacher's ObjectId.")
    else:
        clear_and_import_jobs()