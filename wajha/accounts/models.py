from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.db import models
from django.core.validators import RegexValidator


def validate_cv_file(file):
    if not file.name.lower().endswith('.pdf'):
        raise ValidationError("The file must be in PDF format only.")
    if file.size > 5 * 1024 * 1024:   
        raise ValidationError('The file size must not exceed 5 megabytes.')

full_name_validator = RegexValidator(
    regex=r'^[A-Za-z\u0600-\u06FF]+(?: [A-Za-z\u0600-\u06FF]+)+$',
    message="Please enter your full name (first and last) using letters only, with no numbers, dashes, or special characters."
)
class User(AbstractUser):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('admin', 'Admin'),
    )
    DEGREE_LEVEL_CHOICES = (
        ('bachelor', "Bachelor's"),
        ('master', "Master's"),
        ('phd', 'PhD'),
    )     
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    full_name = models.CharField(max_length=200, blank=True, validators=[full_name_validator])
    country = models.CharField(max_length=100, blank=True)
    field_of_study = models.CharField(max_length=150, blank=True)
    degree_level = models.CharField(max_length=20, choices=DEGREE_LEVEL_CHOICES, blank=True)
    gpa = models.DecimalField(
        max_digits=3, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(4)])  
    languages = models.CharField(max_length=255, blank=True)  
    cv_file = models.FileField(upload_to='cvs/', null=True, blank=True , validators=[validate_cv_file] )
    bio = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.username
    