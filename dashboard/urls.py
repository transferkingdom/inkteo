from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.home, name='home'),
    path('settings/', views.settings, name='settings'),
    path('update-profile/', views.update_profile, name='update_profile'),
    path('update-company/', views.update_company, name='update_company'),
    path('change-password/', views.change_password, name='change_password'),
    path('orders/', views.order_list, name='order_list'),
    path('orders/upload/', views.upload_orders, name='upload_orders'),
    path('orders/<str:order_id>/', views.order_detail, name='order_detail'),
]