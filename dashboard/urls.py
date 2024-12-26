from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.home, name='home'),
    path('settings/', views.settings, name='settings'),
    path('update-profile/', views.update_profile, name='update_profile'),
    path('update-company/', views.update_company, name='update_company'),
]