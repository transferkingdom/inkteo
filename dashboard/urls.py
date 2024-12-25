from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.home, name='home'),
    path('settings/', views.settings, name='settings'),
    path('settings/profile/', views.update_profile, name='update_profile'),
    path('settings/company/', views.update_company, name='update_company'),
]