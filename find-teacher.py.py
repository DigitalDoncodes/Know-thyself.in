#!/usr/bin/env python3
"""
Script to find teacher ObjectId from MongoDB database
Use this to get the correct ObjectId for your job seeding script
"""

from pymongo import MongoClient
from bson import ObjectId
import os
import pytz
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env

def find_teacher_id():
    """
    Find and display all teacher ObjectIds from the database
    """

    # Try different common database names based on your setup
    possible_db_names = ['portal', 'jobportal', 'knowthyself', 'job_portal_app'] # Updated to include new folder name

    # MongoDB connection - adjust if needed
    try:
        # Use MONGO_URI from .env if available, otherwise fallback
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/portal")
        client = MongoClient(mongo_uri)
        print("✅ Connected to MongoDB successfully")

        # Try each possible database name
        db = None
        # If a database name is explicitly in MONGO_URI, use that first
        if "/portal" in mongo_uri: # Simple check for default
            if 'portal' in client.list_collection_names():
                test_db = client['portal']
                if 'users' in test_db.list_collection_names() and test_db.users.count_documents({}) > 0:
                    db = test_db
                    print(f"✅ Found database: portal with {test_db.users.count_documents({})} users")

        if db is None: # If not found by direct URI, try other common names
            for db_name in possible_db_names:
                test_db = client[db_name]
                # Check if this database has a users collection with data
                if 'users' in test_db.list_collection_names():
                    user_count = test_db.users.count_documents({})
                    if user_count > 0:
                        db = test_db
                        print(f"✅ Found database: {db_name} with {user_count} users")
                        break

        if db is None:
            print("❌ Could not find a database with users collection or any data.")
            print("Available databases:", client.list_database_names())
            client.close()
            return

        # Find all users with teacher role
        teachers = list(db.users.find({"role": "teacher"}))

        if teachers:
            print(f"\n🎉 Found {len(teachers)} teacher(s):")
            print("=" * 60)

            for i, teacher in enumerate(teachers, 1):
                print(f"\nTeacher #{i}:")
                print(f"  Name: {teacher.get('name', 'N/A')}")
                print(f"  Email: {teacher.get('email', 'N/A')}")
                print(f"  Student ID: {teacher.get('student_id', 'N/A')}")
                print(f"  Phone: {teacher.get('phone', 'N/A')}")
                print(f"  ObjectId: {teacher['_id']}")
                print(f"  ObjectId (string): '{str(teacher['_id'])}'")
                print("-" * 40)

                # This is what you need to copy for your job seeding script
                print(f"💡 Use this in your script: TEACHER_USER_ID = \"{str(teacher['_id'])}\"")
                print("-" * 40)
        else:
            print("❌ No teachers found in the database")
            print("Checking all users...")
            all_users = list(db.users.find({}))
            if all_users:
                print(f"Found {len(all_users)} total users:")
                for user in all_users:
                    print(f"  - {user.get('name', 'N/A')} ({user.get('email', 'N/A')}) - Role: {user.get('role', 'N/A')}")
            else:
                print("No users found at all!")

        client.close()

    except Exception as e:
        print(f"❌ Error connecting to MongoDB: {e}")
        print("\n💡 Make sure:")
        print("  1. MongoDB is running (mongod service)")
        print("  2. Your .env MONGO_URI is correct")
        print("  3. You have run create_teacher.sh at least once")

def verify_teacher_exists(teacher_id_string):
    """
    Verify that a specific teacher ObjectId exists in the database
    """
    try:
        # Use MONGO_URI from .env if available, otherwise fallback
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/portal")
        client = MongoClient(mongo_uri)

        # Try to find the database
        possible_db_names = ['portal', 'jobportal', 'knowthyself', 'job_portal_app']
        db = None
        if "/portal" in mongo_uri:
            if 'portal' in client.list_database_names():
                db = client['portal']
        if db is None:
            for db_name in possible_db_names:
                test_db = client[db_name]
                if 'users' in test_db.list_collection_names():
                    if test_db.users.count_documents({}) > 0:
                        db = test_db
                        break

        if db is None:
            print("❌ Could not find database or users collection.")
            return False

        # Try to find teacher by ObjectId
        teacher = db.users.find_one({"_id": ObjectId(teacher_id_string), "role": "teacher"})

        if teacher:
            print(f"✅ Teacher found: {teacher.get('name')} ({teacher.get('email')})")
            return True
        else:
            print(f"❌ No teacher found with ObjectId: {teacher_id_string}")
            return False

        client.close()

    except Exception as e:
        print(f"❌ Error verifying teacher: {e}")
        return False

if __name__ == "__main__":
    print("🔎 JobPortal Teacher ID Finder")
    print("=" * 40)

    # Find all teachers
    find_teacher_id()

    print("\n" + "=" * 60)
    print("📝 Next Steps:")
    print("1. Copy the ObjectId string from above")
    print("2. Update your job seeding script (`sed_jobs.py`):")
    print("   TEACHER_USER_ID = \"your_objectid_here\"")
    print("3. Run your job seeding script")
    print("4. Check your teacher dashboard - jobs should now appear!")

    # Optional: Test a specific ObjectId
    # Uncomment the lines below and replace with your ObjectId to test
    # print("\n🧪 Testing specific ObjectId...")
    # verify_teacher_exists("your_objectid_here")