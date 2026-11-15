from datetime import datetime

from mongoengine import (
    Document, EmbeddedDocument,BooleanField,
    StringField, FloatField, IntField, ListField, DateTimeField,
    ReferenceField, EmbeddedDocumentListField, URLField,
)


class Student(Document):
    name = StringField(required=True, max_length=100)
    email = StringField(required=True, unique=True)
    password = StringField(required=True)          # we will store a hash, never plain text
    cgpa = FloatField(required=True, min_value=0, max_value=10)
    branch = StringField(required=True)            # e.g. "AI", "CSE"
    backlogs = IntField(default=0, min_value=0)
    verified = BooleanField(default=False)
    skills = ListField(StringField())              # e.g. ["Python", "Django"]
    resume_link = URLField()

    meta = {"collection": "students", "indexes": ["branch", "cgpa"]}

    def __str__(self):
        return self.name


class Company(Document):
    name = StringField(required=True, max_length=100)
    role = StringField(required=True)
    package_lpa = FloatField(required=True, min_value=0)
    min_cgpa = FloatField(required=True, min_value=0, max_value=10)
    eligible_branches = ListField(StringField())
    required_skills = ListField(StringField())
    max_backlogs = IntField(default=0, min_value=0)  # most backlogs allowed
    deadline = DateTimeField()                        # last date to apply (optional)

    meta = {"collection": "companies", "indexes": ["min_cgpa"]}

    def __str__(self):
        return f"{self.name} - {self.role}"


class Round(EmbeddedDocument):
    name = StringField(required=True)              # "Aptitude", "Technical", "HR"
    result = StringField(choices=["Pending", "Cleared", "Rejected"], default="Pending")


class Application(Document):
    student = ReferenceField(Student, required=True)
    company = ReferenceField(Company, required=True)
    status = StringField(
        choices=["Applied", "Shortlisted", "Selected", "Rejected"],
        default="Applied",
    )
    rounds = EmbeddedDocumentListField(Round)
    applied_date = DateTimeField(default=datetime.now)

    meta = {
        "collection": "applications",
        # one student can apply to a company only once
        "indexes": [{"fields": ["student", "company"], "unique": True}],
    }

    def __str__(self):
        return f"{self.student} -> {self.company}"

class Admin(Document):
    name = StringField(required=True)
    email = StringField(required=True, unique=True)
    password = StringField(required=True)

    meta = {"collection": "admins"}

    def __str__(self):
        return self.name