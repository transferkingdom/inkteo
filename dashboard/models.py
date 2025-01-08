from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.conf import settings
import os

class SearchPattern(models.Model):
    """Model for search patterns"""
    TYPE_CHOICES = [
        ('size', 'Size Pattern'),
        ('color', 'Color Pattern')
    ]
    pattern_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    pattern = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_pattern_type_display()}: {self.pattern}"

    class Meta:
        ordering = ['pattern_type', 'pattern']

def pdf_file_upload_path(instance, filename):
    """PDF dosyası için upload yolunu belirle"""
    # Create path: orders/pdfs/BATCH_ID/filename
    return os.path.join('orders', 'pdfs', str(instance.order_id), filename)

class BatchOrder(models.Model):
    """Batch order model for bulk order uploads"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    order_id = models.CharField(max_length=50, unique=True, editable=False)  # e.g. 1000-20240321153000
    upload_date = models.DateTimeField(auto_now_add=True)
    pdf_file = models.FileField(upload_to=pdf_file_upload_path)
    total_orders = models.IntegerField(default=0)
    total_items = models.IntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=[
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('error', 'Error')
        ],
        default='processing'
    )
    raw_data = models.JSONField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.order_id:
            from .utils import generate_order_id
            self.order_id = generate_order_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Batch {self.order_id}"

    class Meta:
        ordering = ['-upload_date']

class OrderDetail(models.Model):
    """PDF'den okunan her bir sipariş için model"""
    batch = models.ForeignKey(BatchOrder, on_delete=models.CASCADE, related_name='orders')
    etsy_order_number = models.CharField(max_length=50)  # PDF'deki Order #
    customer_name = models.CharField(max_length=100)
    shipping_address = models.TextField()
    order_date = models.DateField()
    shipping_method = models.CharField(max_length=100)
    tracking_number = models.CharField(max_length=100)
    total_items = models.IntegerField(default=0)

    def __str__(self):
        return f"Order {self.etsy_order_number}"

    class Meta:
        ordering = ['id']  # PDF'deki sıraya göre sıralama

def print_image_upload_path(instance, filename):
    """Print image için upload yolunu belirle"""
    # Get batch order ID from the related order
    batch_id = instance.order.batch.order_id
    # Create path: orders/images/BATCH_ID/print_images/filename
    return os.path.join('orders', 'images', str(batch_id), 'print_images', filename)

class OrderItem(models.Model):
    """Order items model"""
    order = models.ForeignKey(OrderDetail, on_delete=models.CASCADE, related_name='items')
    name = models.CharField(max_length=255, default='')
    sku = models.CharField(max_length=50)
    quantity = models.IntegerField(default=1)
    size = models.CharField(max_length=100)
    color = models.CharField(max_length=50)
    personalization = models.CharField(max_length=255, blank=True, null=True)
    image = models.ImageField(upload_to='orders/images/%Y/%m/%d/', null=True, blank=True)
    image_url = models.URLField(null=True, blank=True)  # Original image URL
    print_image = models.CharField(max_length=500, null=True, blank=True)  # Store relative path to print image

    def __str__(self):
        return f"{self.name} - {self.sku}"

    class Meta:
        ordering = ['id']  # PDF'deki sıraya göre sıralama

class PrintImageSettings(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    print_folder_path = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Dropbox API settings
    dropbox_access_token = models.CharField(max_length=255, blank=True, null=True)
    dropbox_refresh_token = models.CharField(max_length=255, blank=True, null=True)
    dropbox_token_expiry = models.DateTimeField(null=True, blank=True)
    dropbox_folder_path = models.CharField(max_length=255, blank=True, null=True, default='/Print Images')
    use_dropbox = models.BooleanField(default=False)

    def __str__(self):
        return f"Print Settings for {self.user.email}"

    class Meta:
        verbose_name = "Print Image Settings"
        verbose_name_plural = "Print Image Settings"
