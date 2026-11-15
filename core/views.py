from datetime import datetime
import csv

from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from django.shortcuts import render, redirect
from mongoengine.errors import ValidationError, NotUniqueError

from .models import Student, Company, Application, Admin, Round
from .services import (
    eligible_companies, skill_match, best_offer,
    placement_by_branch, applications_by_status,
)

BRANCHES = ["AI", "CSE", "IT", "ECE", "EEE", "MECH"]
STATUSES = ["Applied", "Shortlisted", "Selected", "Rejected"]


def current_student(request):
    """Returns the logged-in Student, or None."""
    student_id = request.session.get("student_id")
    return Student.objects(id=student_id).first() if student_id else None


def current_admin(request):
    """Returns the logged-in Admin, or None."""
    admin_id = request.session.get("admin_id")
    return Admin.objects(id=admin_id).first() if admin_id else None


def register(request):
    context = {"branches": BRANCHES, "form": request.POST}

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        branch = request.POST.get("branch", "")
        skills = request.POST.get("skills", "")
        resume_link = request.POST.get("resume_link", "").strip()

        try:
            cgpa = float(request.POST.get("cgpa", ""))
            backlogs = int(request.POST.get("backlogs", "0") or 0)
        except ValueError:
            messages.error(request, "CGPA must be a number and backlogs a whole number.")
            return render(request, "core/register.html", context)

        if not name or not email or branch not in BRANCHES:
            messages.error(request, "Please fill in all the required fields.")
        elif not 0 <= cgpa <= 10 or backlogs < 0:
            messages.error(request, "CGPA must be 0 to 10 and backlogs cannot be negative.")
        elif len(password) < 6:
            messages.error(request, "Password must be at least 6 characters.")
        elif Student.objects(email=email).first():
            messages.error(request, "This email is already registered.")
        else:
            try:
                Student(
                    name=name,
                    email=email,
                    password=make_password(password),   # stored as a hash
                    cgpa=cgpa,
                    branch=branch,
                    backlogs=backlogs,
                    skills=[s.strip() for s in skills.split(",") if s.strip()],
                    resume_link=resume_link or None,
                ).save()
            except ValidationError:
                messages.error(request, "Resume link must be a valid URL.")
                return render(request, "core/register.html", context)

            messages.success(request, "Account created. Please log in.")
            return redirect("login")

    return render(request, "core/register.html", context)


def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")

        student = Student.objects(email=email).first()
        if student and check_password(password, student.password):
            request.session["student_id"] = str(student.id)
            return redirect("home")

        admin = Admin.objects(email=email).first()
        if admin and check_password(password, admin.password):
            request.session["admin_id"] = str(admin.id)
            return redirect("admin_home")

        messages.error(request, "Invalid email or password.")

    return render(request, "core/login.html")


def logout_view(request):
    request.session.flush()
    return redirect("login")


def home(request):
    student = current_student(request)
    if not student:
        return redirect("login")

    my_apps = Application.objects(student=student)
    status_by_company = {str(a.company.id): a.status for a in my_apps}

    drives = []
    for company in eligible_companies(student):
        matched, needed = skill_match(student, company)
        drives.append({
            "company": company,
            "matched": matched,
            "needed": needed,
            "status": status_by_company.get(str(company.id)),   # None if not applied
        })

    return render(request, "core/home.html", {
        "student": student,
        "drives": drives,
        "my_apps": my_apps,
        "offer": best_offer(student),
    })


def apply_to_drive(request, company_id):
    student = current_student(request)
    if not student:
        return redirect("login")
    if request.method != "POST":
        return redirect("home")

    # Re-check eligibility on the server. Never trust the button alone.
    try:
        company = eligible_companies(student).filter(id=company_id).first()
    except ValidationError:
        company = None

    if not company:
        messages.error(request, "You are not eligible for this drive.")
    else:
        try:
            Application(student=student, company=company).save()
            messages.success(request, f"Applied to {company.name}.")
        except NotUniqueError:
            messages.info(request, f"You have already applied to {company.name}.")

    return redirect("home")


def admin_home(request):
    admin = current_admin(request)
    if not admin:
        return redirect("login")        # students and visitors are kept out

    stats = {
        "students": Student.objects.count(),
        "drives": Company.objects.count(),
        "applications": Application.objects.count(),
        "selected": Application.objects(status="Selected").count(),
    }
    return render(request, "core/admin_home.html", {
        "admin": admin,
        "stats": stats,
        "by_branch": placement_by_branch(),
        "by_status": applications_by_status(),
    })


def admin_drives(request):
    if not current_admin(request):
        return redirect("login")

    drives = []
    for company in Company.objects.order_by("name"):
        drives.append({
            "company": company,
            "applicants": Application.objects(company=company).count(),
        })
    return render(request, "core/admin_drives.html", {"drives": drives})


def admin_drive_add(request):
    if not current_admin(request):
        return redirect("login")

    context = {
        "branches": BRANCHES,
        "form": request.POST,
        "selected_branches": request.POST.getlist("branches"),
    }

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        role = request.POST.get("role", "").strip()
        branches = request.POST.getlist("branches")
        skills = request.POST.get("skills", "")
        deadline_raw = request.POST.get("deadline", "")

        try:
            package = float(request.POST.get("package_lpa", ""))
            min_cgpa = float(request.POST.get("min_cgpa", ""))
            max_backlogs = int(request.POST.get("max_backlogs", "0") or 0)
            deadline = None
            if deadline_raw:
                # open until the end of the chosen day
                deadline = datetime.strptime(deadline_raw, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        except ValueError:
            messages.error(request, "Check the numbers and the date.")
            return render(request, "core/admin_drive_form.html", context)

        if not name or not role or not branches:
            messages.error(request, "Enter company, role and select at least one branch.")
        elif not 0 <= min_cgpa <= 10 or package < 0 or max_backlogs < 0:
            messages.error(request, "CGPA must be 0 to 10; package and backlogs cannot be negative.")
        else:
            Company(
                name=name,
                role=role,
                package_lpa=package,
                min_cgpa=min_cgpa,
                max_backlogs=max_backlogs,
                deadline=deadline,
                eligible_branches=branches,
                required_skills=[s.strip() for s in skills.split(",") if s.strip()],
            ).save()
            messages.success(request, f"Drive posted: {name}.")
            return redirect("admin_drives")

    return render(request, "core/admin_drive_form.html", context)

def admin_applicants(request, company_id):
    if not current_admin(request):
        return redirect("login")

    try:
        company = Company.objects(id=company_id).first()
    except ValidationError:
        company = None
    if not company:
        messages.error(request, "Drive not found.")
        return redirect("admin_drives")

    applications = Application.objects(company=company).order_by("-applied_date")
    return render(request, "core/admin_applicants.html", {
        "company": company,
        "applications": applications,
        "statuses": STATUSES,
    })


def admin_update_status(request, application_id):
    if not current_admin(request):
        return redirect("login")
    if request.method != "POST":
        return redirect("admin_drives")

    try:
        application = Application.objects(id=application_id).first()
    except ValidationError:
        application = None

    status = request.POST.get("status", "")
    if not application or status not in STATUSES:
        messages.error(request, "Could not update the application.")
        return redirect("admin_drives")

    application.status = status
    application.save()
    messages.success(request, f"{application.student.name} marked as {status}.")
    return redirect("admin_applicants", company_id=str(application.company.id))

def admin_students(request):
    if not current_admin(request):
        return redirect("login")
    students = Student.objects.order_by("verified", "name")
    return render(request, "core/admin_students.html", {"students": students})


def admin_student_verify(request, student_id):
    if not current_admin(request) or request.method != "POST":
        return redirect("login")
    student = Student.objects(id=student_id).first()
    if student:
        try:
            student.cgpa = float(request.POST["cgpa"])
            student.backlogs = int(request.POST["backlogs"])
            student.verified = True
            student.save()
            messages.success(request, f"{student.name} verified.")
        except (ValueError, ValidationError):
            messages.error(request, "Enter a CGPA between 0 and 10 and a whole number of backlogs.")
    return redirect("admin_students")

def admin_students_import(request):
    if not current_admin(request) or request.method != "POST":
        return redirect("login")
    upload = request.FILES.get("file")
    if not upload:
        messages.error(request, "Choose a CSV file first.")
        return redirect("admin_students")

    lines = upload.read().decode("utf-8-sig").splitlines()
    updated, skipped = 0, []
    for row in csv.DictReader(lines):
        email = (row.get("email") or "").strip()
        try:
            student = Student.objects(email__iexact=email).first()
            if not student:
                skipped.append(email)
                continue
            student.cgpa = float(row["cgpa"])
            student.backlogs = int(row["backlogs"])
            student.verified = True
            student.save()
            updated += 1
        except (KeyError, TypeError, ValueError, ValidationError):
            skipped.append(email or "?")

    messages.success(request, f"{updated} students verified from CSV.")
    if skipped:
        messages.warning(request, "Skipped (not found or bad data): " + ", ".join(skipped))
    return redirect("admin_students")

def admin_add_round(request, application_id):
    if not current_admin(request) or request.method != "POST":
        return redirect("login")
    application = Application.objects(id=application_id).first()
    if not application:
        return redirect("admin_drives")
    name = request.POST.get("name", "").strip()
    if name:
        application.rounds.append(Round(name=name, result="Pending"))
        application.save()
    return redirect("admin_applicants", company_id=str(application.company.id))


def admin_update_round(request, application_id, index):
    if not current_admin(request) or request.method != "POST":
        return redirect("login")
    application = Application.objects(id=application_id).first()
    if not application:
        return redirect("admin_drives")
    result = request.POST.get("result")
    if 0 <= index < len(application.rounds) and result in ("Pending", "Cleared", "Rejected"):
        application.rounds[index].result = result
        application.save()
    return redirect("admin_applicants", company_id=str(application.company.id))