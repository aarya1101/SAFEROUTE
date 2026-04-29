"""
URL configuration for SAFETYNET1 project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from myapp import views


urlpatterns = [

    # -------------------------
    # Admin
    # -------------------------
    path('admin/', admin.site.urls),

    # -------------------------
    # Home
    # -------------------------
    path('', views.index, name="index"),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),

    # -------------------------
    # Authentication
    # -------------------------
    path('login/', views.loginpage, name='login'),
    path('admin-login/', views.admin_login, name='admin_login'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin_dashboard/admin_report/', views.admin_report, name='admin_report'),
    path('admin-reports/', views.admin_report, name='admin_report'),
    path('admin-approved-cases/', views.admin_approved_cases, name='admin_approved_cases'),
    path('approve-report/<int:report_id>/', views.approve_report, name='approve_report'),
    path('delete-report/<int:report_id>/', views.delete_report, name='delete_report'),
    path('assign-officer/<int:report_id>/', views.assign_officer, name='assign_officer'),
    path('signup-citizen/', views.signup_citizen, name="signup_citizen"),
    path('signup-police/', views.signup_police, name="signup_police"),
    path('update-profile/', views.update_profile, name='update_profile'),
    path('choose_pg/', views.choose_pg, name="choose_pg"),

    path('signup_sho/', views.signup_sho, name="signup_sho"),
    path('SHO_dashboard/sho_approved_cases', views.sho_approved_cases, name='sho_approved_cases'),
    path('SHO_dashboard/', views.sho_dashboard, name='sho_dashboard'),

    # -------------------------
    # Citizen Dashboard
    # -------------------------
    path('citizen-home/', views.citizen_home, name='citizen_home'),

    path('approve_police/<int:user_id>/', views.approve_police, name='approve_police'),
    path("disapprove_police/<int:user_id>/", views.disapprove_police, name="disapprove_police"),
    path('police_dashboard/', views.police_dashboard, name='police_dashboard'),
    path('police_performance/', views.police_performance, name='police_performance'),

    # Police update status
    path('update-report-status/<int:report_id>/', views.update_report_status, name='update_report_status'),

    # Police feedback
    path('officer-feedbacks/', views.officer_feedbacks, name='officer_feedbacks'),

    # -------------------------
    # Crime Reporting
    # -------------------------
    path('crime-report/', views.crime_report, name='crime_report'),
    path('anonymous-report/', views.anonymous_report, name='anonymous_report'),
    path('verify_evidence/', views.verify_evidence, name="verify_evidence"),
    path("api/report_crime/", views.report_crime, name="report_crime"),
    path('view-evidence/<int:report_id>/', views.view_evidence, name='view_evidence'),
    #path('give-feedback/', views.give_feedback, name='give_feedback'),
    path('rate-city/', views.rate_city, name='rate_city'),
    path('view-ratings/', views.view_city_ratings, name='view_city_ratings'),

    # -------------------------
    # Safety Analytics
    # -------------------------
    path("safety-check/", views.safety_check, name="safety_check"),
    path('predict-safety/', views.predict_safety_view, name='predict_safety'),
    #path('map-distribution/', views.map_distribution, name='map_distribution'),
    path('safety-predict/', views.safety_predict, name='safety_predict'),
    # #map
    # path('map/', views.map_view, name='map'),
    # path('crime-map-data/', views.crime_map_data, name='crime_map_data'),
 # -------------------------
    # Crime Hotspot Map        ← ADD THIS
    # -------------------------
    path('crime-map/', views.crime_map, name='crime_map'),
    # -------------------------
    # Chatbot App
    # -------------------------
    path('chatbot/', include('chatbot.urls')),
    # ============================================================
# ADD THESE 3 LINES to your urlpatterns list in urls.py
# ============================================================
# (import json at top of views.py if not already there)
 
# In urls.py, inside urlpatterns = [...], add:
 
    # -------------------------
    # SOS System
    # -------------------------
    path('sos/trigger/',           views.sos_trigger,      name='sos_trigger'),
    path('sos/contacts/',          views.manage_contacts,  name='manage_contacts'),
 
]

# Serve media files during development
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)