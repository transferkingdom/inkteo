from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('dashboard', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='printimagesettings',
            name='dropbox_access_token',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='printimagesettings',
            name='dropbox_refresh_token',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='printimagesettings',
            name='dropbox_token_expiry',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='printimagesettings',
            name='dropbox_folder_path',
            field=models.CharField(blank=True, default='/Print Images', max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='printimagesettings',
            name='use_dropbox',
            field=models.BooleanField(default=False),
        ),
    ]
