from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction
from django.db.models import Avg, Q
from asgiref.sync import async_to_sync

import re
import uuid
import json
import base64
import os
import math
import requests
from datetime import timedelta, datetime

from .models import userProfile, CrimeReport, CrimePhoto, EmergencyContact, OfficerFeedback, PoliceStation
from .forms import ProfileForm
from .utils import send_email_to_client
from .utils_pkg.deepfake_detector import is_fake_image, is_fake_video


# ─────────────────────────────────────────────
# INDEX
# ─────────────────────────────────────────────

def index(request):
    return render(request, 'index.html')


# ─────────────────────────────────────────────
# ADMIN
# ─────────────────────────────────────────────

def admin_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        if username == 'aarya1101' and password == 'aarya1101':
            request.session['is_admin'] = True
            messages.success(request, "Admin login successful.")
            return redirect('admin_dashboard')
        else:
            messages.error(request, "Invalid admin credentials.")
    return render(request, 'admin_login.html')


def admin_dashboard(request):
    pending_officers = userProfile.objects.filter(role__iexact='police', is_approved=False, disapproval_message__isnull=True)
    return render(request, 'admin_dashboard.html', {'pending_officers': pending_officers})


def admin_report(request):
    reports = CrimeReport.objects.filter(status="Pending")
    for report in reports:
        if not report.assigned_officer:
            officer = userProfile.objects.filter(role='police', location=report.address).first()
            if officer:
                report.assigned_officer = officer
                report.status = "Assigned"
                report.save()
    return render(request, "admin_report.html", {'reports': reports})


def admin_approved_cases(request):
    reports = CrimeReport.objects.filter(status="Assigned")
    return render(request, "admin_approved_cases.html", {'reports': reports})


def approve_report(request, report_id):
    report = get_object_or_404(CrimeReport, id=report_id)
    report.status = "Assigned"
    report.is_approved = True
    report.save()
    return redirect('admin_report')


def delete_report(request, report_id):
    report = get_object_or_404(CrimeReport, id=report_id)
    report.delete()
    return redirect('admin_report')


def assign_officer(request, report_id):
    report = CrimeReport.objects.get(id=report_id)
    officers = userProfile.objects.filter(role='police', is_approved=True).order_by('-star_rating')
    if request.method == "POST":
        officer_id = request.POST.get('officer')
        officer = userProfile.objects.get(id=officer_id)
        report.assigned_officer = officer
        report.status = "Assigned"
        report.save()
        return redirect('admin_report')
    return render(request, 'assign_officer.html', {'report': report, 'officers': officers})


def approve_police(request, user_id):
    profile = get_object_or_404(userProfile, user__id=user_id)
    profile.is_approved = True
    profile.save()
    messages.success(request, f"Officer <b>{profile.user.username}</b> has been approved.")
    return redirect('admin_dashboard')

def crime_map(request):
    return render(request, 'crimemap.html')

@csrf_exempt
def disapprove_police(request, user_id):
    if request.method == "POST":
        try:
            officer = get_object_or_404(userProfile, user_id=user_id)
            officer.is_approved = False
            officer.disapproval_message = "Your registration has been disapproved by the admin."
            officer.save()
            return JsonResponse({"status": "success", "message": "Officer disapproved successfully!"})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)})
    return JsonResponse({"status": "error", "message": "Invalid request"}, status=400)


# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────

def user_logout(request):
    logout(request)
    return redirect('login')


def loginpage(request):
    try:
        if request.method == 'POST':
            # Use .strip() to handle accidental spaces at the end of the username
            username = request.POST.get('username', '').strip()
            password = request.POST.get('password', '')
            
            # Authenticate checks the hashed password against the database
            user = authenticate(username=username, password=password)
            
            if user is not None:
                profile = userProfile.objects.get(user=user)
                
                # Check for approval for Police/SHO roles [cite: 6, 17]
                if profile.role in ['police', 'sho'] and not profile.is_approved:
                    messages.error(request, "Your account is pending admin approval.")
                    return render(request, 'login.html')

                login(request, user)
                request.session['login_success'] = 'Login successful!'
                
                # Role-based redirection [cite: 9, 10]
                if profile.role == 'citizen':
                    return redirect('citizen_home')
                elif profile.role == 'police':
                    return redirect('police_dashboard')
                elif profile.role == 'sho':
                    return redirect('sho_dashboard')
                else:
                    return redirect('admin_dashboard')
            else:
                messages.error(request, "Invalid Credentials!")
                return render(request, 'login.html')
                
    except userProfile.DoesNotExist:
        messages.error(request, "User profile not found in system.")
        return render(request, 'login.html')
    except Exception as e:
        print(f"Login Error: {e}")
        
    return render(request, 'login.html')


def signuppage(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm-password', '')
        role = request.session.get('user_role', '').strip()

        if not role:
            messages.error(request, "User role is not specified.")
            return render(request, 'signup.html')

        phone = request.POST.get('phone', '').strip() if role.lower() == 'police' else ''

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email is already in use.")
            return render(request, 'signup.html')
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username is already taken.")
            return render(request, 'signup.html')
        if len(password) < 8:
            messages.error(request, "Password must be at least 8 characters long.")
            return render(request, 'signup.html')
        if not re.search(r'[A-Za-z]', password):
            messages.error(request, "Password must contain at least one letter.")
            return render(request, 'signup.html')
        if not re.search(r'[0-9]', password):
            messages.error(request, "Password must contain at least one number.")
            return render(request, 'signup.html')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            messages.error(request, "Password must contain at least one special character.")
            return render(request, 'signup.html')
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'signup.html')

        if role.lower() == 'police':
            if not phone.isdigit():
                messages.error(request, "Phone number must contain only digits.")
                return render(request, 'signup.html')
            if len(phone) != 10:
                messages.error(request, "Phone number must be exactly 10 digits.")
                return render(request, 'signup.html')

        try:
            with transaction.atomic():
                user = User.objects.create_user(username=username, email=email, password=password)
                is_approved = False if role.lower() == 'police' else True
                id_card = request.FILES.get('id_card') if role.lower() == 'police' else None
                userProfile.objects.create(
                    user=user,
                    role=role.lower(),
                    is_approved=is_approved,
                    phone=f"+91{phone}" if role.lower() == 'police' else '',
                    id_card=id_card
                )
                login(request, user)
                messages.success(request, "Account created successfully.")
                return redirect('login')
        except Exception as e:
            print("Signup Error:", e)
            messages.error(request, "An error occurred during signup. Please try again.")

    return render(request, 'signup.html')


from django.db import transaction

from django.db import transaction
from django.contrib.auth import login

def signup_citizen(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm-password', '')
        contact_count = int(request.POST.get('contact_count', 0))

        # 1. Immediate Validation Checks [cite: 21, 22]
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username is already taken.")
            return render(request, 'signup_citizen.html')
        
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'signup_citizen.html')

        # 2. Extract and Validate Emergency Contacts [cite: 24, 25]
        contacts = []
        for i in range(contact_count):
            name = request.POST.get(f'contact_name_{i}', '').strip()
            phone = request.POST.get(f'contact_phone_{i}', '').strip()
            rel = request.POST.get(f'contact_rel_{i}', '').strip()
            if name and phone and len(phone) == 10:
                contacts.append({'name': name, 'phone': phone, 'relationship': rel})

        if len(contacts) < 2:
            messages.error(request, "At least 2 valid emergency contacts are required.")
            return render(request, 'signup_citizen.html')

        # 3. Use an Atomic Transaction to ensure all or nothing 
        try:
            with transaction.atomic():
                # Create the auth user [cite: 25]
                user = User.objects.create_user(
                    username=username, 
                    email=email, 
                    password=password
                )
                
                # Create the associated profile [cite: 25]
                userProfile.objects.create(
                    user=user, 
                    role='citizen', 
                    is_approved=True
                )
                
                # Create the contacts [cite: 26]
                for c in contacts:
                    EmergencyContact.objects.create(
                        user=user, 
                        name=c['name'], 
                        phone=c['phone'], 
                        relationship=c['relationship']
                    )
                
                # IMPORTANT: Establish the session properly 
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                
                messages.success(request, f"Welcome, {username}! Your account is active.")
                return redirect('citizen_home') # Redirect straight to dashboard 

        except Exception as e:
            print(f"CRITICAL SIGNUP ERROR: {e}")
            messages.error(request, "Registration failed due to a system error.")

    return render(request, 'signup_citizen.html')

def signup_police(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm-password')
        id_card = request.FILES.get('id_card')
        phone = request.POST.get('phone', '').strip()
        station_name = request.POST.get('station_name', '').strip()
        badge_id = request.POST.get('badge_id', '').strip()
        experience_level = request.POST.get('experience_level')
        specialty = request.POST.get('specialty')
        live_video_b64 = request.POST.get('liveness_video')
        live_frame_b64 = request.POST.get('liveness_frame')

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email is already in use.")
            return render(request, 'signup_police.html')
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username is already taken.")
            return render(request, 'signup_police.html')
        if len(password) < 8 or not re.search(r'[A-Za-z]', password) or not re.search(r'\d', password):
            messages.error(request, "Password must be at least 8 chars and include letters & numbers.")
            return render(request, 'signup_police.html')
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'signup_police.html')
        if not phone.isdigit() or len(phone) != 10:
            messages.error(request, "Phone must be exactly 10 digits.")
            return render(request, 'signup_police.html')
        if not station_name:
            messages.error(request, "Station name is required.")
            return render(request, 'signup_police.html')
        if not badge_id:
            messages.error(request, "Badge ID is required.")
            return render(request, 'signup_police.html')
        if not experience_level:
            messages.error(request, "Please select your experience level.")
            return render(request, 'signup_police.html')
        if not specialty:
            messages.error(request, "Please select your specialty.")
            return render(request, 'signup_police.html')
        if not live_video_b64 or not live_frame_b64:
            messages.error(request, "Please record the 3-second liveness video first.")
            return render(request, 'signup_police.html')

        try:
            user = User.objects.create_user(username=username, email=email, password=password)
            profile = userProfile.objects.create(
                user=user,
                role='police',
                phone=f"+91{phone}",
                id_card=id_card,
                station_name=station_name,
                badge_id=badge_id,
                experience_level=experience_level,
                specialty=specialty,
                is_approved=False
            )

            from django.core.files.base import ContentFile
            header, data = live_video_b64.split(';base64,')
            ext = header.split('/')[-1]
            video_data = base64.b64decode(data)
            profile.liveness_video.save(f"{username}_live.{ext}", ContentFile(video_data), save=False)

            header, data = live_frame_b64.split(';base64,')
            ext = header.split('/')[-1]
            img_data = base64.b64decode(data)
            profile.liveness_frame.save(f"{username}_frame.{ext}", ContentFile(img_data), save=False)

            profile.save()
            login(request, user)
            request.session['login_success'] = "Account created successfully! Please log in to continue."
            return redirect('login')
        except Exception as e:
            print("Police Signup Error:", e)
            messages.error(request, "An error occurred during signup. Please try again.")

    return render(request, 'signup_police.html')


def signup_sho(request):
    stations = PoliceStation.objects.all()

    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm-password')
        id_card = request.FILES.get('id_card')
        phone = request.POST.get('phone', '').strip()
        station_id = request.POST.get('station', '').strip()
        badge_id = request.POST.get('badge_id', '').strip()
        experience_level = request.POST.get('experience_level')
        specialty = request.POST.get('specialty')
        live_video_b64 = request.POST.get('liveness_video')
        live_frame_b64 = request.POST.get('liveness_frame')

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email is already in use.")
            return render(request, 'signup_sho.html', {"stations": stations})
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username is already taken.")
            return render(request, 'signup_sho.html', {"stations": stations})
        if len(password) < 8 or not re.search(r'[A-Za-z]', password) or not re.search(r'\d', password):
            messages.error(request, "Password must be at least 8 characters and include letters & numbers.")
            return render(request, 'signup_sho.html', {"stations": stations})
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'signup_sho.html', {"stations": stations})
        if not phone.isdigit() or len(phone) != 10:
            messages.error(request, "Phone must be exactly 10 digits.")
            return render(request, 'signup_sho.html', {"stations": stations})
        if not station_id:
            messages.error(request, "Please select your police station.")
            return render(request, 'signup_sho.html', {"stations": stations})
        if not badge_id:
            messages.error(request, "Badge ID is required.")
            return render(request, 'signup_sho.html', {"stations": stations})
        if not experience_level:
            messages.error(request, "Please select your experience level.")
            return render(request, 'signup_sho.html', {"stations": stations})
        if not specialty:
            messages.error(request, "Please select your specialty.")
            return render(request, 'signup_sho.html', {"stations": stations})
        if not live_video_b64 or not live_frame_b64:
            messages.error(request, "Please record the 3-second liveness video first.")
            return render(request, 'signup_sho.html', {"stations": stations})

        try:
            from django.core.files.base import ContentFile
            station_instance = PoliceStation.objects.get(id=station_id)
            user = User.objects.create_user(username=username, email=email, password=password)
            user.save()

            profile = userProfile.objects.create(
                user=user,
                role='sho',
                phone=f"+91{phone}",
                id_card=id_card,
                station=station_instance,
                badge_id=badge_id,
                experience_level=experience_level,
                specialty=specialty,
                is_approved=False
            )

            header, data = live_video_b64.split(';base64,')
            ext = header.split('/')[-1]
            video_data = base64.b64decode(data)
            profile.liveness_video.save(f"{username}_live.{ext}", ContentFile(video_data), save=False)

            header, data = live_frame_b64.split(';base64,')
            ext = header.split('/')[-1]
            img_data = base64.b64decode(data)
            profile.liveness_frame.save(f"{username}_frame.{ext}", ContentFile(img_data), save=False)

            profile.save()
            login(request, user)
            request.session['login_success'] = 'SHO Account Created Successfully. Please Login to continue'
            return redirect('login')
        except PoliceStation.DoesNotExist:
            messages.error(request, "Invalid police station selected.")
        except Exception as e:
            print("SHO Signup Error:", e)
            messages.error(request, "An error occurred during signup. Please try again.")

    return render(request, 'signup_sho.html', {"stations": stations})


def choose_pg(request):
    if request.method == 'POST':
        role = request.POST.get('role')
        request.session['user_role'] = role
        if role == 'police':
            return redirect('signup_police')
        else:
            return redirect('signup_citizen')
    return render(request, 'choose_pg.html')


# ─────────────────────────────────────────────
# PROFILE
# ─────────────────────────────────────────────

@csrf_exempt
def update_profile(request):
    if request.method == "POST":
        try:
            data = request.POST
            profile = request.user.userprofile
            profile.contact = data.get("contact", profile.contact)
            profile.address = data.get("address", profile.address)
            profile.location = data.get("location", profile.location)
            request.user.first_name = data.get("first_name", request.user.first_name)
            request.user.last_name = data.get("last_name", request.user.last_name)
            if 'profile_image' in request.FILES:
                profile.profile_image = request.FILES['profile_image']
            request.user.save()
            profile.save()
            return JsonResponse({
                "status": "success",
                "message": "Profile updated successfully!",
                "profile_image_url": profile.profile_image.url if profile.profile_image else ""
            })
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)})
    return JsonResponse({"status": "error", "message": "Invalid request"}, status=400)


# ─────────────────────────────────────────────
# CITIZEN HOME
# ─────────────────────────────────────────────

def citizen_home(request):
    return render(request, 'citizen_home.html')


# ─────────────────────────────────────────────
# SOS  ← FINAL WORKING VERSION (SMS ENABLED)
# ─────────────────────────────────────────────

@login_required
@require_POST
def sos_trigger(request):
    try:
        import requests

        data = json.loads(request.body)
        lat  = data.get("latitude")
        lng  = data.get("longitude")

        if lat is None or lng is None:
            return JsonResponse({
                "success": False,
                "message": "Location data missing."
            }, status=400)

        contacts = EmergencyContact.objects.filter(user=request.user)
        sent_to  = contacts.count()

        # ✅ SEND SMS TO ALL CONTACTS
        for contact in contacts:
            url = "https://www.fast2sms.com/dev/bulkV2"

            # ✅ FIX PHONE FORMAT (REMOVE +91 IF PRESENT)
            phone = str(contact.phone).replace("+91", "").strip()

            message = f"SOS ALERT! {request.user.username} needs help. Location: https://maps.google.com/?q={lat},{lng}"

            payload = {
                "sender_id": "TXTIND",
                "message": message,
                "language": "english",
                "route": "q",
                "numbers": phone
            }

            headers = {
                # ❗ REPLACE WITH YOUR NEW VALID API KEY
                "authorization": "8L1irVyUbCDujR9GhoIAx5S3FaXnEMNmkPfK0BtsdWclO7zpq4ZAbjqSkehnPicxIu3lJmgwr0XN75D6",
                "Content-Type": "application/json"
            }

            response = requests.post(url, json=payload, headers=headers)

            print("PHONE:", phone)
            print("SMS RESPONSE:", response.text)

        return JsonResponse({
            "success": True,
            "sent_to": sent_to
        })

    except json.JSONDecodeError:
        return JsonResponse({
            "success": False,
            "message": "Invalid JSON body."
        }, status=400)

    except Exception as e:
        print("SOS ERROR:", e)
        return JsonResponse({
            "success": False,
            "message": str(e)
        }, status=500)
# ─────────────────────────────────────────────
# EMERGENCY CONTACTS
# ─────────────────────────────────────────────

@login_required
def manage_contacts(request):
    contacts = EmergencyContact.objects.filter(user=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'delete':
            contact_id = request.POST.get('contact_id')
            if contacts.count() <= 2:
                messages.error(request, "You must keep at least 2 emergency contacts.")
            else:
                EmergencyContact.objects.filter(id=contact_id, user=request.user).delete()
                messages.success(request, "Contact removed.")
            return redirect('manage_contacts')

        elif action == 'add':
            if contacts.count() >= 3:
                messages.error(request, "Maximum 3 emergency contacts allowed.")
            else:
                name  = request.POST.get('name', '').strip()
                phone = request.POST.get('phone', '').strip()
                rel   = request.POST.get('relationship', '').strip()
                if not name or not phone or len(phone) != 10 or not phone.isdigit():
                    messages.error(request, "Please provide a valid name and 10-digit phone number.")
                else:
                    EmergencyContact.objects.create(user=request.user, name=name, phone=phone, relationship=rel)
                    messages.success(request, f"{name} added as emergency contact.")
            return redirect('manage_contacts')

        elif action == 'edit':
            contact_id = request.POST.get('contact_id')
            name  = request.POST.get('name', '').strip()
            phone = request.POST.get('phone', '').strip()
            rel   = request.POST.get('relationship', '').strip()
            if not name or not phone or len(phone) != 10 or not phone.isdigit():
                messages.error(request, "Please provide a valid name and 10-digit phone number.")
            else:
                EmergencyContact.objects.filter(id=contact_id, user=request.user).update(
                    name=name, phone=phone, relationship=rel
                )
                messages.success(request, "Contact updated.")
            return redirect('manage_contacts')

    return render(request, 'manage_contacts.html', {'contacts': contacts})


# ─────────────────────────────────────────────
# CRIME REPORTING
# ─────────────────────────────────────────────

def crime_report(request):
    return render(request, "crime_report.html")


@csrf_exempt
def report_crime(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request!"})

    try:
        is_authenticated = request.user.is_authenticated

        if not is_authenticated:
            if not request.session.get("anonymous_verified"):
                return JsonResponse({"success": False, "message": "Captcha verification required."})

        crime_type      = request.POST.get("crime_type")
        description     = request.POST.get("description")
        address         = request.POST.get("address", "Unknown")
        latitude        = request.POST.get("latitude")
        longitude       = request.POST.get("longitude")
        video           = request.FILES.get("video")
        incident_date   = request.POST.get("incident_date") or None
        incident_time   = request.POST.get("incident_time") or None
        victim_age_group = request.POST.get("victim_age_group")
        photos          = request.FILES.getlist("photos")
        reported_by     = request.user if is_authenticated else None
        ip_address      = request.META.get("REMOTE_ADDR")

        if not crime_type or not description:
            return JsonResponse({"success": False, "message": "Crime type and description are required."})

        if CrimeReport.objects.filter(crime_type=crime_type, description=description, address=address).exists():
            return JsonResponse({"success": False, "message": "This crime report already exists!"})

        ai_status = "Verified" if is_authenticated else "Pending Verification"

        crime_report_obj = CrimeReport.objects.create(
            crime_type=crime_type,
            description=description,
            address=address,
            latitude=latitude,
            longitude=longitude,
            video=video,
            date_of_incident=incident_date,
            time_of_incident=incident_time,
            victim_age_group=victim_age_group,
            reported_by=reported_by,
            ai_status=ai_status,
            ip_address=ip_address if not is_authenticated else None
        )

        for photo in photos:
            CrimePhoto.objects.create(crime_report=crime_report_obj, photos=photo)

        if not is_authenticated and "anonymous_verified" in request.session:
            del request.session["anonymous_verified"]

        return JsonResponse({"success": True, "message": "Crime report submitted successfully!", "report_id": crime_report_obj.id})

    except Exception as e:
        print("ERROR IN REPORT SUBMISSION:", str(e))
        return JsonResponse({"success": False, "message": f"Error: {str(e)}"})


def anonymous_report(request):
    if request.method == "POST":
        captcha_response = request.POST.get("g-recaptcha-response")
        if not captcha_response:
            messages.error(request, "Please complete the CAPTCHA.")
            return redirect("anonymous_report")

        r = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={"secret": settings.RECAPTCHA_SECRET_KEY, "response": captcha_response}
        )
        result = r.json()

        if result.get("success"):
            request.session['anonymous_verified'] = True
            return redirect("crime_report")
        else:
            messages.error(request, "CAPTCHA verification failed. Try again.")
            return redirect("anonymous_report")

    return render(request, "anonymous_report.html", {"site_key": settings.RECAPTCHA_SITE_KEY})


MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

@csrf_exempt
def verify_evidence(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request method. Use POST."})

    try:
        photos = request.FILES.getlist("photos")
        video  = request.FILES.get("video")

        if not photos and not video:
            return JsonResponse({"success": False, "message": "No evidence files provided."})

        all_files = list(photos) + ([video] if video else [])
        for media in all_files:
            if media and media.size > MAX_FILE_SIZE:
                return JsonResponse({
                    "success": False,
                    "message": f"File '{media.name}' exceeds the {MAX_FILE_SIZE // (1024 * 1024)}MB size limit."
                })

        temp_dir = os.path.join(settings.MEDIA_ROOT, "temp")
        os.makedirs(temp_dir, exist_ok=True)

        for photo in photos:
            temp_path = os.path.join(temp_dir, photo.name)
            with open(temp_path, "wb+") as dest:
                for chunk in photo.chunks():
                    dest.write(chunk)
            if is_fake_image(temp_path):
                return JsonResponse({"success": False, "message": f"❌ Fake/AI-generated photo detected: {photo.name}"})

        if video:
            temp_path = os.path.join(temp_dir, video.name)
            with open(temp_path, "wb+") as dest:
                for chunk in video.chunks():
                    dest.write(chunk)
            if is_fake_video(temp_path):
                return JsonResponse({"success": False, "message": f"❌ Fake/AI-generated video detected: {video.name}"})

        return JsonResponse({"success": True, "message": "✅ All evidence verified as authentic."})

    except Exception as e:
        return JsonResponse({"success": False, "message": f"Error: {str(e)}"})


@csrf_exempt
def view_evidence(request, report_id):
    if request.method == "GET":
        try:
            report    = CrimeReport.objects.get(id=report_id)
            video_url = report.video.url if report.video else None
            photo_urls = [photo.photos.url for photo in report.photos.all()]
            return JsonResponse({"video_url": video_url, "photo_urls": photo_urls})
        except CrimeReport.DoesNotExist:
            return JsonResponse({"error": "Report not found"}, status=404)
    return JsonResponse({"error": "Invalid request"}, status=400)


# ─────────────────────────────────────────────
# SAFETY ANALYTICS
# ─────────────────────────────────────────────

import pandas as pd
from .utils import predict_safety_django, df_long
from .predictor import predict_safety


def safety_check(request):
    df = pd.read_csv('myapp/Allyearcrime.csv')
    df.columns = df.columns.str.strip()
    df['YEAR'] = df['YEAR'].astype(str).str.replace('.0', '', regex=False)

    districts = sorted(df['State/District'].dropna().unique().tolist())
    years     = sorted(df['YEAR'].dropna().unique().tolist())

    selected_district = request.GET.get('district')
    selected_year     = request.GET.get('year')

    filtered_df = df.copy()
    if selected_district:
        filtered_df = filtered_df[filtered_df['State/District'] == selected_district]
    if selected_year:
        filtered_df['YEAR'] = filtered_df['YEAR'].astype(str).str.replace('.0', '', regex=False)
        filtered_df = filtered_df[filtered_df['YEAR'] == str(selected_year)]

    trend_col    = 'Total_Crimes' if 'Total_Crimes' in df.columns else 'Total_Crimes '
    exclude_cols = ['State/District', 'YEAR', trend_col, 'Severe_Crimes', 'Safety_Label']
    crime_cols   = [col for col in df.columns if col not in exclude_cols and pd.api.types.is_numeric_dtype(df[col])]

    crime_trend   = df.groupby('YEAR')[trend_col].sum().reset_index()
    trend_labels  = crime_trend['YEAR'].tolist()
    trend_values  = crime_trend[trend_col].tolist()

    unsafe_df     = df.groupby('State/District')['Severe_Crimes'].sum().reset_index()
    unsafe_labels = unsafe_df['State/District'].tolist()
    unsafe_values = unsafe_df['Severe_Crimes'].tolist()

    crime_totals  = filtered_df[crime_cols].sum().sort_values(ascending=False)
    crime_types   = crime_totals.index.tolist()
    crime_counts  = crime_totals.values.tolist()

    yearly_variation = df.groupby('YEAR')[crime_cols].sum().reset_index()
    yearly_labels    = yearly_variation['YEAR'].tolist()
    yearly_values    = yearly_variation.drop(columns='YEAR').to_dict(orient='list')

    safety_counts = df['Safety_Label'].value_counts().to_dict()
    safety_labels = list(safety_counts.keys())
    safety_values = list(safety_counts.values())

    top_severe          = unsafe_df.sort_values('Severe_Crimes', ascending=False).head(10)
    top_districts_labels = top_severe['State/District'].tolist()
    top_districts_values = top_severe['Severe_Crimes'].tolist()

    radar_data = {}
    for district in districts:
        temp = df[df['State/District'] == district]
        radar_data[district] = temp[crime_cols].sum().tolist()

    context = {
        'districts': districts, 'years': years,
        'trend_labels': trend_labels, 'trend_values': trend_values,
        'unsafe_labels': unsafe_labels, 'unsafe_values': unsafe_values,
        'crime_types': crime_types, 'crime_counts': crime_counts,
        'yearly_labels': yearly_labels, 'yearly_values': yearly_values,
        'safety_labels': safety_labels, 'safety_values': safety_values,
        'top_districts_labels': top_districts_labels, 'top_districts_values': top_districts_values,
        'radar_data': radar_data,
        'selected_district': selected_district, 'selected_year': selected_year,
    }
    return render(request, 'safety_check.html', context)


@csrf_exempt
def predict_safety_view(request):
    if request.method == "POST":
        data   = json.loads(request.body)
        result = predict_safety(data)
        return JsonResponse(result)
    return JsonResponse({"error": "Only POST allowed"}, status=405)


def map_distribution(request):
    df = pd.read_csv('myapp/Allyearcrime.csv')
    df.columns = df.columns.str.strip()

    districts = sorted(df['State/District'].dropna().unique().tolist())
    years     = sorted(df['YEAR'].dropna().unique().tolist())

    selected_district = request.GET.get('district', None)
    selected_year     = request.GET.get('year', None)
    filtered_df = df.copy()
    if selected_district:
        filtered_df = filtered_df[filtered_df['State/District'] == selected_district]
    if selected_year:
        filtered_df['YEAR'] = filtered_df['YEAR'].astype(str).str.replace('.0', '', regex=False)
        filtered_df = filtered_df[filtered_df['YEAR'] == str(selected_year)]

    trend_col    = 'Total_Crimes' if 'Total_Crimes' in df.columns else 'Total_Crimes '
    crime_trend  = df.groupby('YEAR')[trend_col].sum().reset_index()
    trend_labels = crime_trend['YEAR'].tolist()
    trend_values = crime_trend[trend_col].tolist()

    unsafe_df     = df.groupby('State/District')['Severe_Crimes'].sum().reset_index()
    unsafe_labels = unsafe_df['State/District'].tolist()
    unsafe_values = unsafe_df['Severe_Crimes'].tolist()

    exclude_cols = ['State/District', 'YEAR', trend_col, 'Severe_Crimes', 'Safety_Label']
    crime_cols   = [col for col in df.columns if col not in exclude_cols and pd.api.types.is_numeric_dtype(df[col])]
    crime_totals = df[crime_cols].sum().sort_values(ascending=False)
    crime_types  = crime_totals.index.tolist()
    crime_counts = crime_totals.values.tolist()

    yearly_variation = df.groupby('YEAR')[crime_cols].sum().reset_index()
    yearly_labels    = yearly_variation['YEAR'].tolist()
    yearly_values    = yearly_variation.drop(columns='YEAR').to_dict(orient='list')

    safety_counts = df['Safety_Label'].value_counts().to_dict()
    safety_labels = list(safety_counts.keys())
    safety_values = list(safety_counts.values())

    top_severe           = unsafe_df.sort_values('Severe_Crimes', ascending=False).head(10)
    top_districts_labels = top_severe['State/District'].tolist()
    top_districts_values = top_severe['Severe_Crimes'].tolist()

    radar_data = {}
    for district in districts:
        temp = df[df['State/District'] == district]
        radar_data[district] = temp[crime_cols].sum().tolist()

    context = {
        'districts': districts, 'years': years,
        'trend_labels': trend_labels, 'trend_values': trend_values,
        'unsafe_labels': unsafe_labels, 'unsafe_values': unsafe_values,
        'crime_types': crime_types, 'crime_counts': crime_counts,
        'yearly_labels': yearly_labels, 'yearly_values': yearly_values,
        'safety_labels': safety_labels, 'safety_values': safety_values,
        'top_districts_labels': top_districts_labels, 'top_districts_values': top_districts_values,
        'radar_data': radar_data,
        'selected_district': selected_district, 'selected_year': selected_year,
    }
    return render(request, 'map.html')


#def map_view(request):
    #return render(request, 'map.html')


# def crime_map_data(request):
#     year       = request.GET.get('year')
#     crime_type = request.GET.get('crime_type')
#     df         = pd.read_csv('crime_data/Allyearcrime.csv')

#     if year:
#         df = df[df['Year'] == int(year)]

#     if crime_type and crime_type != "Total":
#         df           = df.groupby('District')[crime_type].sum().reset_index()
#         crime_column = crime_type
#     else:
#         df           = df.groupby('District')['Total'].sum().reset_index()
#         crime_column = 'Total'

#     data = {}
#     for _, row in df.iterrows():
#         district        = str(row['District']).strip().lower()
#         data[district]  = int(row[crime_column])

#     return JsonResponse(data)

from django.shortcuts import render

def give_feedback(request):
    return render(request, 'givefeedback.html')
def safety_predict(request):
    result              = None
    trend_data          = None
    selected_district   = None
    selected_crime_type = None

    df_long_clean = df_long.dropna(subset=['State/District', 'Crime_Type'])
    districts     = sorted(df_long_clean['State/District'].astype(str).unique())
    crime_types   = sorted(df_long_clean['Crime_Type'].astype(str).unique())

    if request.method == 'POST':
        selected_district   = request.POST.get('district')
        selected_crime_type = request.POST.get('crime_type')
        result              = predict_safety_django(selected_district, selected_crime_type)

        df_trend = df_long_clean[
            (df_long_clean['State/District'] == selected_district) &
            (df_long_clean['Crime_Type'] == selected_crime_type)
        ]
        df_trend   = df_trend.groupby('Year')['Crime_Count'].mean().reset_index()
        trend_data = json.dumps({'years': df_trend['Year'].tolist(), 'counts': df_trend['Crime_Count'].tolist()})

    context = {
        'result': result, 'districts': districts, 'crime_types': crime_types,
        'trend_data': trend_data,
        'selected_district': selected_district, 'selected_crime_type': selected_crime_type,
    }
    return render(request, 'safety_prediction.html', context)

#rate_city 
import pandas as pd
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import CityRating

from django.shortcuts import render, redirect
from django.contrib import messages
from .models import CityRating
import pandas as pd

def rate_city(request):
    # Load districts from CSV for the dropdown
    df = pd.read_csv('myapp/Allyearcrime.csv')
    df.columns = df.columns.str.strip()
    districts = sorted(df['State/District'].dropna().unique().tolist())

    if request.method == "POST":
        district = request.POST.get('district')
        stars = request.POST.get('rating')
        review = request.POST.get('review')
        
        # Save the rating to the database
        CityRating.objects.create(
            district_name=district,
            user=request.user,
            rating=stars,
            review_text=review
        )
        
        # Add the success message
        messages.success(request, f"Rating for {district} submitted successfully!")
        
        # Redirect back to the same page (Rate the City)
        return redirect('rate_city')
        
    return render(request, 'rate_city.html', {'districts': districts})
#view_city_ratings 
import pandas as pd
from django.shortcuts import render, redirect
from django.db.models import Avg
from .models import CityRating



def view_city_ratings(request):
    # Load all districts for the dropdown (same logic as rate_city)
    df = pd.read_csv('myapp/Allyearcrime.csv')
    df.columns = df.columns.str.strip()
    districts = sorted(df['State/District'].dropna().unique().tolist())

    # Get the selected district from the GET request
    selected_district = request.GET.get('district')
    
    # Calculate average ratings (keep this global so users can see the table)
    stats = CityRating.objects.values('district_name').annotate(
        avg_rating=Avg('rating')
    ).order_by('-avg_rating')

    # Filter reviews ONLY if a district is selected
    recent_reviews = None
    if selected_district:
        recent_reviews = CityRating.objects.filter(district_name=selected_district).order_by('-created_at')

    return render(request, 'view_city_ratings.html', {
        'districts': districts,
        'stats': stats,
        'recent_reviews': recent_reviews,
        'selected_district': selected_district
    })
# ─────────────────────────────────────────────
# POLICE / SHO DASHBOARDS
# ─────────────────────────────────────────────

from .utils import officer_score


@login_required
def police_dashboard(request):
    if not request.user.is_authenticated:
        return redirect('login')

    profile = get_object_or_404(userProfile, user=request.user)

    if profile.role.lower() != 'police':
        messages.error(request, "Access denied: You are not a police officer.")
        return redirect('index')

    assigned_reports  = CrimeReport.objects.filter(assigned_officer=profile)
    total_cnt         = assigned_reports.count()
    pending_cnt       = assigned_reports.filter(resolution_status='Pending').count()
    investigating_cnt = assigned_reports.filter(resolution_status='Under Investigation').count()
    resolved_cnt      = assigned_reports.filter(resolution_status='Resolved', resolved_at__isnull=False).count()

    responded = assigned_reports.filter(assigned_at__isnull=False, first_touched_at__isnull=False)
    if responded.exists():
        deltas       = [(r.first_touched_at - r.assigned_at).total_seconds() for r in responded]
        avg_secs     = sum(deltas) / len(deltas)
        avg_response = timedelta(seconds=avg_secs)
    else:
        avg_secs     = 0
        avg_response = None

    avg             = OfficerFeedback.objects.filter(officer=profile).aggregate(a=Avg('rating'))['a']
    officer_rating  = round(avg or 0, 1)
    full_stars      = int(officer_rating)
    partial_percent = int((officer_rating - full_stars) * 100)
    resolution_rate = round((resolved_cnt / total_cnt * 100), 1) if total_cnt else 0

    context = {
        'is_approved':      profile.is_approved,
        'assigned_reports': assigned_reports.exclude(status="Resolved"),
        'officer_profile':  profile,
        'performance': {
            'total': total_cnt, 'pending': pending_cnt,
            'investigating': investigating_cnt, 'resolved': resolved_cnt,
            'avg_response': avg_response, 'avg_response_secs': avg_secs,
        },
        'officer_rating': officer_rating, 'full_stars': full_stars,
        'partial_percent': partial_percent,
        'metrics': {
            'total_cases': total_cnt,
            'case_breakdown': f"{pending_cnt} pending, {investigating_cnt} under investigation, {resolved_cnt} resolved",
            'resolution_rate': resolution_rate,
            'resolution_comment': "Above station average" if resolution_rate > 80 else "Below station average",
        },
    }
    return render(request, 'police_dashboard.html', context)


@login_required
def police_performance(request):
    profile = get_object_or_404(userProfile, user=request.user)

    if profile.role != 'police':
        messages.error(request, "Access denied: You are not a police officer.")
        return redirect('crime_chart')
    if not profile.is_approved:
        messages.error(request, "Your police account is not yet approved.")
        return redirect('police_dashboard')

    reports           = CrimeReport.objects.filter(assigned_officer=profile)
    total_cnt         = reports.count()
    pending_cnt       = reports.filter(resolution_status='Pending').count()
    investigating_cnt = reports.filter(resolution_status='Under Investigation').count()
    resolved_cnt      = reports.filter(resolution_status='Resolved', resolved_at__isnull=False).count()

    responded = reports.filter(assigned_at__isnull=False, first_touched_at__isnull=False)
    if responded.exists():
        deltas       = [(r.first_touched_at - r.assigned_at).total_seconds() for r in responded]
        avg_secs     = sum(deltas) / len(deltas)
        avg_response = timedelta(seconds=avg_secs)
    else:
        avg_secs     = 0
        avg_response = None

    avg             = OfficerFeedback.objects.filter(officer=profile).aggregate(a=Avg('rating'))['a']
    officer_rating  = round(avg or 0, 1)
    full_stars      = math.floor(officer_rating)
    partial_percent = int((officer_rating - full_stars) * 100)
    resolution_rate = round((resolved_cnt / total_cnt * 100), 1) if total_cnt else 0

    context = {
        'officer_profile': profile,
        'performance': {
            'total': total_cnt, 'pending': pending_cnt,
            'investigating': investigating_cnt, 'resolved': resolved_cnt,
            'avg_response': avg_response, 'avg_response_secs': avg_secs,
        },
        'officer_rating': officer_rating, 'full_stars': full_stars,
        'partial_percent': partial_percent,
        'metrics': {
            'total_cases': total_cnt,
            'case_breakdown': f"{pending_cnt} pending, {investigating_cnt} under investigation, {resolved_cnt} resolved",
            'resolution_rate': resolution_rate,
            'resolution_comment': "Above station average" if resolution_rate > 80 else "Below station average",
        },
    }
    return render(request, 'police_performance.html', context)


@login_required
def officer_feedbacks(request):
    profile = get_object_or_404(userProfile, user=request.user)

    if profile.role != 'police':
        messages.error(request, "Access denied: You are not a police officer.")
        return redirect('crime_chart')
    if not profile.is_approved:
        messages.error(request, "Your police account is not yet approved.")
        return redirect('police_dashboard')

    officer         = request.user.userprofile
    feedbacks       = OfficerFeedback.objects.filter(officer=officer).select_related('crime_report')
    avg             = OfficerFeedback.objects.filter(officer=profile).aggregate(a=Avg('rating'))['a']
    officer_rating  = round(avg or 0, 1)
    full_stars      = math.floor(officer_rating)
    partial_percent = int((officer_rating - full_stars) * 100)

    context = {
        'feedbacks': feedbacks,
        'officer_rating': officer_rating, 'full_stars': full_stars,
        'partial_percent': partial_percent,
    }
    return render(request, 'officer_feedbacks.html', context)


def update_report_status(request, report_id):
    if request.method == "POST":
        new_res = request.POST.get("resolution_status")
        report  = get_object_or_404(CrimeReport, id=report_id)

        if report.first_touched_at is None:
            report.first_touched_at = timezone.now()

        report.resolution_status = new_res

        if new_res == "Resolved" and report.resolved_at is None:
            report.resolved_at = timezone.now()

        report.save(update_fields=['first_touched_at', 'resolution_status', 'resolved_at'])

    return redirect('police_dashboard')


def sho_dashboard(request):
    sho_profile  = userProfile.objects.get(user=request.user)
    station      = sho_profile.station
    reports      = CrimeReport.objects.filter(status="Pending", station=station)
    officers_qs  = userProfile.objects.filter(station=station, role='police', is_approved=True)
    total_officers = officers_qs.count()
    on_duty        = officers_qs.filter(is_on_duty=True).count()
    off_duty       = total_officers - on_duty

    officers = []
    for officer in officers_qs:
        total_cases    = CrimeReport.objects.filter(assigned_officer=officer).count()
        resolved_cases = CrimeReport.objects.filter(assigned_officer=officer, resolution_status="Resolved").count()
        pending_cases  = total_cases - resolved_cases
        officer_resolution_rate = round((resolved_cases / total_cases * 100), 1) if total_cases > 0 else 0
        officers.append({
            'id': officer.id, 'name': officer.user.get_full_name(),
            'username': officer.user.username,
            'status': 'on_duty' if officer.is_on_duty else 'off_duty',
            'total_cases': total_cases, 'resolved_cases': resolved_cases,
            'pending_cases': pending_cases, 'resolution_rate': officer_resolution_rate,
        })

    active_cases         = sum(o['total_cases'] for o in officers)
    all_station_cases    = CrimeReport.objects.filter(station=station)
    resolved_station_cases = all_station_cases.filter(resolution_status="Resolved").count()
    station_resolution_rate = round((resolved_station_cases / all_station_cases.count() * 100), 1) if all_station_cases.exists() else 0

    context = {
        "officers": officers, "total_officers": total_officers,
        "on_duty": on_duty, "off_duty": off_duty,
        "reports": reports, "active_cases": active_cases,
        "station_resolution_rate": station_resolution_rate,
    }
    return render(request, "sho_police_dashboard.html", context)


def sho_approved_cases(request):
    sho_profile = request.user.userprofile
    reports = CrimeReport.objects.filter(
        status="Approved", station=sho_profile.station, assigned_officer__isnull=True
    )
    officers = userProfile.objects.filter(role='police', is_approved=True, station=sho_profile.station)

    for rpt in reports:
        scored = [(o, officer_score(o, rpt.crime_type)) for o in officers]
        scored.sort(key=lambda x: x[1], reverse=True)
        rpt.scored_officers = scored

    if request.method == "POST":
        report_id  = request.POST.get('report_id')
        officer_id = request.POST.get('officer_id')
        rpt        = get_object_or_404(CrimeReport, id=report_id)
        off        = get_object_or_404(userProfile, id=officer_id)
        rpt.assigned_officer = off
        rpt.assigned_at      = timezone.now()
        rpt.save()
        messages.success(request, f"Assigned to Officer {off.user.username}!")
        return redirect('sho_approved_cases')

    return render(request, "sho_approved_cases.html", {'reports': reports})


# ─────────────────────────────────────────────
# ABOUT & CONTACT
# ─────────────────────────────────────────────

def about(request):
    return render(request, 'about.html')


def contact(request):
    if request.method == 'POST':
        messages.success(request, 'Message sent successfully.')
        return redirect('contact')
    return render(request, 'contact.html')