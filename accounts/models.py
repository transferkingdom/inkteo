from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = (
        ('admin', 'Admin'),
        ('pod_admin', 'POD Admin'),
        ('pod_printer', 'POD Printer'),
        ('pod_production', 'POD Production'),
        ('user', 'User'),
    )
    
    user_type = models.CharField(
        max_length=20,
        choices=USER_TYPE_CHOICES,
        default='user'
    )
    
    def __str__(self):
        return self.email
