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
    logger.debug("Password change signal received")
    
    try:
        current_site = Site.objects.get_current()
        login_url = f"https://{current_site.domain}{reverse('account_login')}"
        logger.debug(f"Login URL generated: {login_url}")
        
        context = {
            'user': user,
            'login_url': login_url,
        }
        logger.debug(f"Email context prepared: {context}")
        
        # HTML email template render
        try:
            html_message = render_to_string('account/email/password_changed_confirmation.html', context)
            logger.debug("HTML template rendered successfully")
        except Exception as template_error:
            logger.error(f"Template rendering error: {str(template_error)}")
            raise
        
        # Email gönderme
        try:
            send_mail(
                subject='Inkteo - Password Changed Successfully',
                message='Your password has been changed successfully.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )
            logger.info(f"Password change confirmation email sent to {user.email}")
            
        except Exception as email_error:
            logger.error(f"Email sending error: {str(email_error)}")
            logger.error(f"Email settings: FROM={settings.DEFAULT_FROM_EMAIL}, TO={user.email}")
            raise
            
    except Exception as e:
        logger.error(f"General error in password change notification: {str(e)}")
        logger.exception("Full traceback:")