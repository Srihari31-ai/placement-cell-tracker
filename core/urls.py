from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("apply/<str:company_id>/", views.apply_to_drive, name="apply"),
    path("manage/", views.admin_home, name="admin_home"),
    path("manage/drives/", views.admin_drives, name="admin_drives"),
    path("manage/drives/add/", views.admin_drive_add, name="admin_drive_add"),
    path("manage/drives/<str:company_id>/applicants/", views.admin_applicants, name="admin_applicants"),
    path("manage/applications/<str:application_id>/status/", views.admin_update_status, name="admin_update_status"),
    path("manage/students/", views.admin_students, name="admin_students"),
    path("manage/students/<str:student_id>/verify/", views.admin_student_verify, name="admin_student_verify"),
    path("manage/students/import/", views.admin_students_import, name="admin_students_import"),
    path("manage/applications/<str:application_id>/rounds/add/", views.admin_add_round, name="admin_add_round"),
    path("manage/applications/<str:application_id>/rounds/<int:index>/", views.admin_update_round,
         name="admin_update_round"),
]