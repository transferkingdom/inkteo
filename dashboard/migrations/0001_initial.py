# Generated by Django 5.1.3 on 2025-01-08 19:34

import dashboard.models
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BatchOrder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order_id', models.CharField(editable=False, max_length=50, unique=True)),
                ('upload_date', models.DateTimeField(auto_now_add=True)),
                ('pdf_file', models.FileField(upload_to=dashboard.models.pdf_file_upload_path)),
                ('total_orders', models.IntegerField(default=0)),
                ('total_items', models.IntegerField(default=0)),
                ('status', models.CharField(choices=[('processing', 'Processing'), ('completed', 'Completed'), ('error', 'Error')], default='processing', max_length=20)),
                ('raw_data', models.JSONField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-upload_date'],
            },
        ),
        migrations.CreateModel(
            name='SearchPattern',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pattern_type', models.CharField(choices=[('size', 'Size Pattern'), ('color', 'Color Pattern')], max_length=20)),
                ('pattern', models.CharField(max_length=100)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['pattern_type', 'pattern'],
            },
        ),
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
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Print Image Settings',
                'verbose_name_plural': 'Print Image Settings',
            },
        ),
        migrations.CreateModel(
            name='OrderDetail',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('etsy_order_number', models.CharField(max_length=50)),
                ('customer_name', models.CharField(max_length=100)),
                ('shipping_address', models.TextField()),
                ('order_date', models.DateField()),
                ('shipping_method', models.CharField(max_length=100)),
                ('tracking_number', models.CharField(max_length=100)),
                ('total_items', models.IntegerField(default=0)),
                ('batch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='orders', to='dashboard.batchorder')),
            ],
            options={
                'ordering': ['id'],
            },
        ),
        migrations.CreateModel(
            name='OrderItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='', max_length=255)),
                ('sku', models.CharField(max_length=50)),
                ('quantity', models.IntegerField(default=1)),
                ('size', models.CharField(max_length=100)),
                ('color', models.CharField(max_length=50)),
                ('personalization', models.CharField(blank=True, max_length=255, null=True)),
                ('image', models.ImageField(blank=True, null=True, upload_to='orders/images/%Y/%m/%d/')),
                ('image_url', models.URLField(blank=True, null=True)),
                ('print_image', models.CharField(blank=True, max_length=500, null=True)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='dashboard.orderdetail')),
            ],
            options={
                'ordering': ['id'],
            },
        ),
    ]
