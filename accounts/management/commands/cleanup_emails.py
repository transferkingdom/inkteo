from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from allauth.account.models import EmailAddress

User = get_user_model()

class Command(BaseCommand):
    help = 'Cleanup multiple email addresses and ensure one primary email per user'

    def handle(self, *args, **kwargs):
        for user in User.objects.all():
            # Delete all email addresses for user
            EmailAddress.objects.filter(user=user).delete()
            
            # Create single primary email
            EmailAddress.objects.create(
                user=user,
                email=user.email,
                primary=True,
                verified=True
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully cleaned up emails for user: {user.email}')
            ) 