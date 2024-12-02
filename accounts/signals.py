from django.dispatch import receiver
from django.db.models.signals import post_save
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=get_user_model())
def notify_password_change(sender, instance, created, **kwargs):
    if not created and instance.has_usable_password():  # Yeni kullanıcı değilse ve şifre değişmişse
        print(f"Password change detected for user: {instance.email}")
        logger.info(f"Password change detected for user: {instance.email}")
        
        try:
            # Basit bir email gönder
            send_mail(
                subject='Inkteo - Password Changed Successfully',
                message='''
                Your password has been changed successfully.
                
                If you did not make this change, please contact us immediately.
                
                Best regards,
                Inkteo Team
                ''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.email],
                fail_silently=False,
            )
            print(f"Password change email sent to {instance.email}")
            logger.info(f"Password change email sent to {instance.email}")
            
        except Exception as e:
            print(f"Error sending password change email: {str(e)}")
            logger.error(f"Error sending password change email: {str(e)}")