from django.dispatch import receiver
from django.core.mail import send_mail
from django.contrib.sites.models import Site
from django.urls import reverse
from django.conf import settings
from allauth.account.signals import password_set, password_changed, password_reset
import logging

logger = logging.getLogger(__name__)

def send_password_change_email(user):
    """Email gönderme fonksiyonu"""
    try:
        current_site = Site.objects.get_current()
        login_url = f"https://{current_site.domain}{reverse('account_login')}"
        
        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                .button {{
                    background-color: #9BD5E8;
                    border: none;
                    color: white;
                    padding: 15px 32px;
                    text-align: center;
                    text-decoration: none;
                    display: inline-block;
                    font-size: 16px;
                    margin: 4px 2px;
                    cursor: pointer;
                    border-radius: 4px;
                }}
            </style>
        </head>
        <body>
            <h2>Password Changed Successfully</h2>
            <p>Your password has been changed successfully.</p>
            <p>You can now sign in to your account using your new password.</p>
            <p><a href="{login_url}" class="button" style="color: white;">Sign In</a></p>
            <p>If you did not make this change, please contact us immediately.</p>
            <br>
            <p>Best regards,<br>Inkteo Team</p>
        </body>
        </html>
        """
        
        send_mail(
            subject='Inkteo - Password Changed Successfully',
            message='Your password has been changed successfully.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Password change email sent to {user.email}")
        
    except Exception as e:
        logger.error(f"Error sending password change email: {str(e)}")

@receiver(password_changed)
def on_password_changed(sender, request, user, **kwargs):
    send_password_change_email(user)

@receiver(password_set)
def on_password_set(sender, request, user, **kwargs):
    send_password_change_email(user)

@receiver(password_reset)
def on_password_reset(sender, request, user, **kwargs):
    send_password_change_email(user)