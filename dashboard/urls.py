from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.home, name='home'),
    path('orders/', views.orders, name='orders'),
    path('orders/upload/', views.upload_orders, name='upload_orders'),
    path('orders/<str:order_id>/', views.order_detail, name='order_detail'),
    path('settings/', views.settings_view, name='settings'),
    path('settings/print-image/', views.print_image_settings, name='print_image_settings'),
    path('settings/dropbox/auth/', views.dropbox_auth, name='dropbox_auth'),
    path('settings/dropbox/callback/', views.dropbox_callback, name='dropbox_callback'),
    path('settings/dropbox/disconnect/', views.dropbox_disconnect, name='dropbox_disconnect'),
    path('settings/update-profile/', views.update_profile, name='update_profile'),
    path('settings/update-company/', views.update_company, name='update_company'),
    path('settings/change-password/', views.change_password, name='change_password'),
<<<<<<< HEAD
=======
    path('settings/print-image/', views.print_image_settings, name='print_image_settings'),
    path('orders/', views.order_list, name='order_list'),
    path('orders/upload/', views.upload_orders, name='upload_orders'),
    path('orders/<str:order_id>/', views.order_detail, name='order_detail'),
    path('settings/select-print-folder/', views.select_print_folder, name='select_print_folder'),
    path('settings/dropbox/auth/', views.dropbox_auth, name='dropbox_auth'),
    path('settings/dropbox/callback/', views.dropbox_callback, name='dropbox_callback'),
    path('settings/dropbox/disconnect/', views.dropbox_disconnect, name='dropbox_disconnect'),
>>>>>>> 9df032bef5d97a8d6078ead9ca087434a48ae28f
]