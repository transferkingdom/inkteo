from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.contrib.sites.models import Site
from allauth.account.signals import password_changed
from django.conf import settings
import logging

# Logger oluştur
logger = logging.getLogger(__name__)

@receiver(password_changed)
def notify_password_change(sender, request, user, **kwargs):
    try:
        current_site = Site.objects.get_current()
        login_url = f"https://{current_site.domain}{reverse('account_login')}"
        
        # HTML email
        html_message = render_to_string('account/email/password_changed_confirmation.html', {
            'user': user,
            'login_url': login_url,
        })
        
        # Send email
        send_mail(
            subject='Inkteo - Password Changed Successfully',
            message='Your password has been changed successfully.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Password change confirmation email sent to {user.email}")
        
    except Exception as e:
        logger.error(f"Error sending password change email: {str(e)}")