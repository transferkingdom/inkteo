from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.home, name='home'),
    path('settings/', views.settings_view, name='settings'),
    path('settings/update-profile/', views.update_profile, name='update_profile'),
    path('settings/update-company/', views.update_company, name='update_company'),
    path('settings/change-password/', views.change_password, name='change_password'),
    path('settings/print-image/', views.print_image_settings, name='print_image_settings'),
    path('orders/', views.order_list, name='order_list'),
    path('orders/upload/', views.upload_orders, name='upload_orders'),
    path('orders/<str:order_id>/', views.order_detail, name='order_detail'),
    path('settings/select-print-folder/', views.select_print_folder, name='select_print_folder'),
]