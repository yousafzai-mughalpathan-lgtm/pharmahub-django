# authentication/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

from django.contrib.auth.models import AbstractUser, BaseUserManager

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        # Superuser ke liye role automatically admin set hoga
        extra_fields.setdefault('role', 'admin')

        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
    # Email ko unique rakhna lazmi hai agar aap usay login ke liye use kar rahe hain.
    email = models.EmailField(unique=True) 
    # Username ko unique=False aur blank=True karein takay error na aaye
    username = models.CharField(max_length=150, unique=False, null=True, blank=True) 
     
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('super_admin', 'Super Admin'),
        ('customer', 'Customer'),
        ('pharmacy', 'Pharmacy'),
        ('pharmacist', 'Pharmacist'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer')
    # --- New Field for Pharmacy License ---
    license = models.CharField(max_length=255, null=True, blank=True) 
    # optional document for pharmacists/pharmacies
    license_document = models.FileField(upload_to='licenses/', null=True, blank=True)
    # pharmacist approval flag
    is_verified_pharmacist = models.BooleanField(default=False)
    # Security tracking
    last_login_ip = models.GenericIPAddressField(blank=True, null=True)
    failed_login_attempts = models.IntegerField(default=0)
    lockout_until = models.DateTimeField(null=True, blank=True)
    last_failed_login = models.DateTimeField(blank=True, null=True)

    # Django ko batana ke ab username ki jagah email use hogi
    USERNAME_FIELD = 'email' 
    REQUIRED_FIELDS = ['username'] # Email ke ilawa jo cheez lazmi chahiye

    objects = CustomUserManager() # Ye line add karein takay hum apna custom manager use kar saken

    @property
    def is_admin_user(self):
        return self.role in ['super_admin', 'admin']

    @property
    def is_pharmacist_user(self):
        return self.role in ['pharmacist', 'pharmacy']

    @property
    def is_customer_user(self):
        return self.role == 'customer'

    def __str__(self):
        return f"{self.email} ({self.role})"
