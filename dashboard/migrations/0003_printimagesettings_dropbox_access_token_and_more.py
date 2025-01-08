from django.db import migrations, models
from django.conf import settings

class Migration(migrations.Migration):
    dependencies = [
        ('dashboard', '0002_alter_batchorder_pdf_file'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PrintImageSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('print_folder_path', models.CharField(blank=True, max_length=255, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('dropbox_access_token', models.CharField(blank=True, max_length=255, null=True)),
                ('dropbox_refresh_token', models.CharField(blank=True, max_length=255, null=True)),
                ('dropbox_token_expiry', models.DateTimeField(blank=True, null=True)),
                ('dropbox_folder_path', models.CharField(blank=True, default='/Print Images', max_length=255, null=True)),
                ('use_dropbox', models.BooleanField(default=False)),
                ('user', models.OneToOneField(on_delete=models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Print Image Settings',
                'verbose_name_plural': 'Print Image Settings',
            },
        ),
    ]
