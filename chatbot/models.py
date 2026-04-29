from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import User

class IPCSection(models.Model):
    section_number = models.CharField(max_length=20)
    title = models.CharField(max_length=255)
    description = models.TextField()
    punishment = models.TextField()
    keywords = models.TextField()

    def __str__(self):
        return f"Section {self.section_number} - {self.title}"


class SafetyGuideline(models.Model):
    category = models.CharField(max_length=100)
    advice = models.TextField()

    def __str__(self):
        return self.category


class ChatLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    intent = models.CharField(max_length=100)
    response = models.TextField()
    severity_score = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.intent}"
