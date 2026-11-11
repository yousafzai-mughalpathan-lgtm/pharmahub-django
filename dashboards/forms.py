# dashboards/forms.py

from django import forms
from .models import Medicine

# dashboards/forms.py

class MedicineForm(forms.ModelForm):
    CATEGORY_CHOICES = [
        ('Antibiotics', 'Antibiotics'),
        ('Antihistamine', 'Antihistamine'),
        ('Painkillers', 'Painkillers'),
        ('Maternal Health', 'Maternal & Pregnancy'),
        ('Heart & BP', 'Heart & BP'),
        ('Diabetic Care', 'Diabetes / Sugar'),
        ('Vitamins', 'Vitamins & Supplements'),
        ('Skincare', 'Skincare & Haircare'),
        ('Baby Care', 'Baby Care'),
        ('General Items', 'General Items'),
    ]
    
    category = forms.ChoiceField(
        choices=CATEGORY_CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 rounded-lg border border-gray-200 outline-none focus:border-blue-500',
            'id': 'medCategory' # Id lazmi add karein
        })
    )
    # ... baki code same rahega

    class Meta:
        model = Medicine
        # 'image' ko fields mein shamil karna sab se zaroori tha
        fields = [
            'name', 'brand', 'category', 'price', 
            'stock_quantity', 'expiry_date', 'batch_number', 
            'description', 'image'
        ]
        
        # HTML elements ko style dene ke liye widgets
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 rounded-lg border border-gray-200 outline-none focus:border-blue-500', 
                'placeholder': 'Enter medicine name'
            }),
            'brand': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 rounded-lg border border-gray-200 outline-none focus:border-blue-500', 
                'placeholder': 'Brand name'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 rounded-lg border border-gray-200 outline-none focus:border-blue-500', 
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'stock_quantity': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 rounded-lg border border-gray-200 outline-none focus:border-blue-500', 
                'placeholder': '0'
            }),
            'expiry_date': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2 rounded-lg border border-gray-200 outline-none focus:border-blue-500', 
                'type': 'date'
            }),
            'batch_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 rounded-lg border border-gray-200 outline-none focus:border-blue-500', 
                'placeholder': 'Batch number'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 rounded-lg border border-gray-200 outline-none focus:border-blue-500', 
                'placeholder': 'Medicine description', 
                'rows': 2
            }),
            # Image input ke liye styling
            'image': forms.FileInput(attrs={
                'class': 'w-full px-4 py-2 rounded-lg border border-gray-200 outline-none focus:border-blue-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100',
                'accept': 'image/*'
            }),
        }
        
        labels = {
            'stock_quantity': 'Stock Quantity',
            'image': 'Medicine Image',
        }