from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from allauth.account.models import EmailAddress
from django.utils.html import format_html

# EmailAddress için özel admin
class EmailAddressAdmin(admin.ModelAdmin):
    list_display = ('email', 'user', 'verified', 'primary', 'verification_status')
    list_filter = ('verified', 'primary')
    search_fields = ('email', 'user__email')
    raw_id_fields = ('user',)
    actions = ['make_verified', 'make_unverified', 'make_primary']

    def verification_status(self, obj):
        if obj.verified:
            return format_html('<span style="color: green;">✓ Verified</span>')
        return format_html('<span style="color: red;">✗ Unverified</span>')
    verification_status.short_description = 'Status'

    def make_verified(self, request, queryset):
        queryset.update(verified=True)
    make_verified.short_description = "Mark selected emails as verified"

    def make_unverified(self, request, queryset):
        queryset.update(verified=False)
    make_unverified.short_description = "Mark selected emails as unverified"

    def make_primary(self, request, queryset):
        for email_address in queryset:
            # Önce diğer tüm emailleri primary olmaktan çıkar
            EmailAddress.objects.filter(user=email_address.user).update(primary=False)
            # Seçili emaili primary yap
            email_address.primary = True
            email_address.save()
    make_primary.short_description = "Set selected email as primary"

# Mevcut User admin'e email verification bilgisini ekle
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'email_verified')
    list_filter = UserAdmin.list_filter + ('emailaddress__verified',)

    def email_verified(self, obj):
        email_address = EmailAddress.objects.filter(user=obj, primary=True).first()
        if email_address and email_address.verified:
            return format_html('<span style="color: green;">✓ Verified</span>')
        return format_html('<span style="color: red;">✗ Unverified</span>')
    email_verified.short_description = 'Email Status'

# Admin kayıtları
admin.site.unregister(User)  # Önce varsayılan User admin'i kaldır
admin.site.register(User, CustomUserAdmin)  # Özelleştirilmiş User admin'i ekle
admin.site.register(EmailAddress, EmailAddressAdmin)  # EmailAddress admin'i ekle