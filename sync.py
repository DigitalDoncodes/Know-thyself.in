from pymongo import MongoClient
from bson.objectid import ObjectId

client = MongoClient("mongodb://localhost:27017/")
db = client["portal"]

# --- Fix jobs collection ---
for job in db.jobs.find():
    updates = {}

    # Rename "desc" -> "description"
    if "desc" in job and "description" not in job:
        updates["description"] = job["desc"]

    # Rename "slots" -> "vacancies"
    if "slots" in job and "vacancies" not in job:
        updates["vacancies"] = job["slots"]

    # Ensure vacancies field exists
    if "vacancies" not in job:
        updates["vacancies"] = 0

    if updates:
        db.jobs.update_one({"_id": job["_id"]}, {"$set": updates})
        print(f"Updated job {job['_id']} with {updates}")

# --- Fix applications collection ---
for app in db.applications.find():
    # Ensure applicant_id is a string (Flask uses string version of ObjectId)
    if isinstance(app.get("applicant_id"), ObjectId):
        str_id = str(app["applicant_id"])
        db.applications.update_one(
            {"_id": app["_id"]},
            {"$set": {"applicant_id": str_id}}
        )
        print(f"Converted applicant_id to string for application {app['_id']}")

    # Ensure job_id is stored as ObjectId
    if isinstance(app.get("job_id"), str):
        try:
            obj_id = ObjectId(app["job_id"])
            db.applications.update_one(
                {"_id": app["_id"]},
                {"$set": {"job_id": obj_id}}
            )
            print(f"Converted job_id to ObjectId for application {app['_id']}")
        except Exception:
            pass

print("✅ Sync complete. Your data is now dashboard-compatible!")