from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.contrib.sites.models import Site
from allauth.account.signals import password_changed

@receiver(password_changed)
def notify_password_change(sender, request, user, **kwargs):
    current_site = Site.objects.get_current()
    login_url = f"https://{current_site.domain}{reverse('account_login')}"
    
    # HTML email
    html_message = render_to_string('account/email/password_changed_confirmation.html', {
        'user': user,
        'login_url': login_url,
    })
    
    # Send email
    send_mail(
        subject='Password Changed Successfully',
        message='Your password has been changed successfully.',
        from_email=None,  # settings.py'daki DEFAULT_FROM_EMAIL kullanılacak
        recipient_list=[user.email],
        html_message=html_message
    )