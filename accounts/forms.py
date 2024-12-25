from django import forms
from .models import CustomUser, Company

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email']

class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ['name', 'tax_id', 'address'] 