from django import models
from django import forms
from .models import Pharmacy

# Pharmacy data handle karne ke liye form
class PharmacyForm(forms.ModelForm):
    class Meta:
        model = Pharmacy
        fields = ['name', 'owner_name', 'license_number', 'is_verified']