from django.db import models
from django.contrib.auth.models import User


# ==========================
# USER PROFILE
# ==========================
class userProfile(models.Model):
    ROLE_CHOICES = [
        ('user', 'User'),
        ('police', 'Police'),
        ('sho', 'SHO'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    forgot_password_token = models.CharField(max_length=255, blank=True, null=True)
    bio = models.TextField(max_length=500, blank=True)
    about = models.TextField(blank=True, null=True)
    contact = models.CharField(max_length=10, blank=True, null=True)
    mail = models.EmailField(blank=True, null=True)

    SPECIALTY_CHOICES = (
        ('Cyber Crime', 'Cyber Crime'),
        ('Theft', 'Theft'),
        ('Assault', 'Assault'),
        ('Fraud', 'Fraud'),
        ('Narcotics', 'Narcotics'),
        ('Other', 'Other'),
    )

    EXPERIENCE_CHOICES = (
        ('Junior', 'Junior'),
        ('Senior', 'Senior'),
        ('Inspector', 'Inspector'),
    )

    address = models.TextField(blank=True, null=True)
    location = models.CharField(max_length=30, blank=True)
    profile_image = models.ImageField(upload_to='profile_images/', blank=True)

    role = models.CharField(max_length=10, choices=ROLE_CHOICES, null=True, blank=True)

    # Police-specific fields
    badge_id = models.CharField(max_length=50, blank=True, null=True)
    station_name = models.CharField(max_length=100, blank=True, null=True)
    experience_level = models.CharField(max_length=20, choices=EXPERIENCE_CHOICES, blank=True, null=True)
    specialty = models.CharField(max_length=50, choices=SPECIALTY_CHOICES, blank=True, null=True)
    rank = models.CharField(max_length=50, blank=True, null=True)

    is_approved = models.BooleanField(default=True)
    disapproval_message = models.TextField(blank=True, null=True)

    phone = models.CharField(max_length=10, blank=True, null=True)
    id_card = models.ImageField(upload_to='id_cards/', blank=True, null=True)

    liveness_video = models.FileField(upload_to='liveness_videos/', blank=True, null=True)
    liveness_frame = models.ImageField(upload_to='liveness_frames/', blank=True, null=True)
    # Rating fields for police officers
    star_rating = models.FloatField(default=0)
    total_ratings = models.IntegerField(default=0)
    cases_completed = models.IntegerField(default=0)


    def __str__(self):
        return f"{self.user.username} ({self.role})"



# ==========================
# ✅ EMERGENCY CONTACT (NEW)
# ==========================
class EmergencyContact(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="emergency_contacts")
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    relationship = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.phone}) - {self.user.username}"


# ==========================
# CRIME REPORT
# ==========================
class CrimeReport(models.Model):
    crime_type = models.CharField(max_length=255)
    description = models.TextField()
    address = models.CharField(max_length=255, default="Unknown")

    latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)

    video = models.FileField(upload_to='crime_videos/', blank=True, null=True)
    date_of_incident = models.DateField()
    time_of_incident = models.TimeField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    AGE_GROUP_CHOICES = [
        ('under_18', 'Under 18'),
        ('18_25', '18-25'),
        ('26_40', '26-40'),
        ('41_60', '41-60'),
        ('above_60', 'Above 60'),
    ]

    victim_age_group = models.CharField(max_length=20, choices=AGE_GROUP_CHOICES)

    reported_at = models.DateTimeField(auto_now_add=True)
    reported_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)

    resolved_at = models.DateTimeField(null=True, blank=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    first_touched_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=[
            ("Pending", "Pending"),
            ("Approved", "Approved"),
            ("Rejected", "Rejected")
        ],
        default="Pending"
    )

    resolution_status = models.CharField(
        max_length=30,
        choices=[
            ("Pending", "Pending"),
            ("Under Investigation", "Under Investigation"),
            ("Resolved", "Resolved"),
        ],
        default="Pending",
    )

    assigned_officer = models.ForeignKey(
        'userProfile', null=True, blank=True, on_delete=models.SET_NULL
    )

    severity_score = models.FloatField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)

    ai_status = models.CharField(max_length=50, default="Pending")
    ai_progress = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.crime_type} - {self.address}"


# ==========================
# CRIME PHOTO
# ==========================
class CrimePhoto(models.Model):
    crime_report = models.ForeignKey(CrimeReport, on_delete=models.CASCADE, related_name='photos')
    photos = models.ImageField(upload_to='photos/')

    is_ai_generated = models.BooleanField(default=False)
    verification_status = models.CharField(
        max_length=20,
        choices=[
            ("Pending", "Pending"),
            ("Verified", "Verified"),
            ("Flagged", "Flagged")
        ],
        default="Pending"
    )

    def __str__(self):
        return f"Photo for Report ID {self.crime_report.id}"


# ==========================
# FEEDBACK
# ==========================
class OfficerFeedback(models.Model):
    crime_report = models.OneToOneField(CrimeReport, on_delete=models.CASCADE)
    officer = models.ForeignKey(userProfile, on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField(default=3)
    comment = models.TextField(blank=True)

    def __str__(self):
        return f"Feedback for {self.officer.user.username}"


# ==========================
# POLICE STATION
# ==========================
class PoliceStation(models.Model):
    name = models.CharField(max_length=255, unique=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name
    

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator

class CityRating(models.Model):
    district_name = models.CharField(max_length=100)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    review_text = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.district_name} - {self.rating} Stars"