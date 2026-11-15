from .models import Company, Student, Application
from datetime import datetime
from mongoengine import Q

def best_offer(student):
    """Highest package (LPA) among this student's Selected applications, or 0."""
    best = 0
    for app in Application.objects(student=student, status="Selected"):
        best = max(best, app.company.package_lpa)
    return best

def eligible_companies(student):
    """Drives this student qualifies for: CGPA, branch, backlogs, deadline,
    and (if already placed) only drives paying more than the current offer."""
    if not student.verified:
        return Company.objects.none()
    drives = Company.objects(
        Q(deadline=None) | Q(deadline__gte=datetime.now()),   # no deadline, or still open
        min_cgpa__lte=student.cgpa,
        eligible_branches=student.branch,
        max_backlogs__gte=student.backlogs,
    )
    offer = best_offer(student)
    if offer > 0:
        drives = drives.filter(package_lpa__gt=offer)
    return drives


def skill_match(student, company):
    """Returns (skills matched, skills required), e.g. (2, 3)."""
    mine = {s.strip().lower() for s in student.skills}
    needed = {s.strip().lower() for s in company.required_skills}
    return len(mine & needed), len(needed)

# ---------- Analytics (MongoDB aggregation pipelines) ----------

def applications_by_status():
    """How many applications are Applied / Shortlisted / Selected / Rejected."""
    pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        {"$addFields": {"status": "$_id"}},
        {"$sort": {"count": -1}},
    ]
    return list(Application.objects.aggregate(pipeline))


def placement_by_branch():
    """Placement % per branch: students with at least one 'Selected' application."""
    pipeline = [
        {"$lookup": {
            "from": "applications",
            "localField": "_id",
            "foreignField": "student",
            "as": "apps",
        }},
        {"$addFields": {"is_placed": {"$gt": [
            {"$size": {"$filter": {
                "input": "$apps",
                "cond": {"$eq": ["$$this.status", "Selected"]},
            }}}, 0]}}},
        {"$group": {
            "_id": "$branch",
            "total": {"$sum": 1},
            "placed": {"$sum": {"$cond": ["$is_placed", 1, 0]}},
        }},
        {"$addFields": {"percent": {"$round": [
            {"$multiply": [{"$divide": ["$placed", "$total"]}, 100]}, 1]}}},
        {"$addFields": {"branch": "$_id"}},
        {"$sort": {"_id": 1}},
    ]
    return list(Student.objects.aggregate(pipeline))


def avg_package_by_branch():
    """Average package (LPA) of selected students, per branch."""
    pipeline = [
        {"$match": {"status": "Selected"}},
        {"$lookup": {"from": "students", "localField": "student",
                     "foreignField": "_id", "as": "s"}},
        {"$lookup": {"from": "companies", "localField": "company",
                     "foreignField": "_id", "as": "c"}},
        {"$unwind": "$s"},
        {"$unwind": "$c"},
        {"$group": {
            "_id": "$s.branch",
            "avg_package": {"$avg": "$c.package_lpa"},
            "offers": {"$sum": 1},
        }},
        {"$sort": {"avg_package": -1}},
    ]
    return list(Application.objects.aggregate(pipeline))