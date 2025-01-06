from django import forms
from .models import PrintImageSettings

class PrintImageSettingsForm(forms.ModelForm):
    class Meta:
        model = PrintImageSettings
        fields = ['print_folder_path']
        widgets = {
            'print_folder_path': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'id_print_folder_path',
                'readonly': True
            })
        } 