# Generated by Django 5.1.3 on 2025-01-10 18:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0003_orderbatch_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderdetail',
            name='qr_code_url',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
