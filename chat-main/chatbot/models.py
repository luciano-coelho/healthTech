from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    reset_password = models.BooleanField(default=False)


class Teacher(models.Model):
    name = models.CharField(max_length=255)
    education = models.CharField(max_length=255)
    area = models.CharField(max_length=255)
    competency = models.CharField(max_length=255)

    def __str__(self):
        return self.name

class Briefing(models.Model):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=255)
    email = models.EmailField()
    question_1 = models.CharField(max_length=255)
    question_2 = models.CharField(max_length=255)
    question_3 = models.CharField(max_length=255)
    question_4 = models.CharField(max_length=255)
    question_5 = models.CharField(max_length=255)
    question_6 = models.CharField(max_length=255)
    question_7 = models.CharField(max_length=255)
    question_8 = models.CharField(max_length=255)
    question_9 = models.CharField(max_length=255)
    question_10 = models.CharField(max_length=255)
    question_11 = models.CharField(max_length=255)
    question_12 = models.CharField(max_length=255)
    question_13 = models.CharField(max_length=255)
    question_14 = models.CharField(max_length=255)
    question_15 = models.CharField(max_length=255)
    question_16 = models.CharField(max_length=255)
    question_17 = models.CharField(max_length=255)
    question_18 = models.CharField(max_length=255)
    question_19 = models.CharField(max_length=255)
    question_20 = models.CharField(max_length=255)
    question_21 = models.CharField(max_length=255)
    question_22 = models.CharField(max_length=255)
    question_23 = models.CharField(max_length=255)
    question_24 = models.CharField(max_length=255)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, blank=True)

    def __str__(self):
        return self.email