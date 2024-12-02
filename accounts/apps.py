from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        print("Loading accounts signals...")
        try:
            from . import signals
            print("Accounts signals loaded successfully")
        except Exception as e:
            print(f"Error loading accounts signals: {str(e)}")
