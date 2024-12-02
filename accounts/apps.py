from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        try:
            import accounts.signals
            print("Signals imported successfully")  # Debug için
        except Exception as e:
            print(f"Error importing signals: {str(e)}")  # Debug için
