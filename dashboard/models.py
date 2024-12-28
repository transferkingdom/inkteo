from django.db import models
from django.utils import timezone

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

class BatchOrder(models.Model):
    """Batch order model for bulk order uploads"""
    order_id = models.CharField(max_length=50, unique=True)  # e.g. 1000-20240321153000
    upload_date = models.DateTimeField(auto_now_add=True)
    pdf_file = models.FileField(upload_to='orders/pdfs/%Y/%m/%d/')
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

class OrderItem(models.Model):
    """Order items model"""
    order = models.ForeignKey(OrderDetail, on_delete=models.CASCADE, related_name='items')
    product_name = models.CharField(max_length=255)
    sku = models.CharField(max_length=50)
    quantity = models.IntegerField(default=1)
    size = models.CharField(max_length=100)
    color = models.CharField(max_length=50)
    personalization = models.CharField(max_length=255, blank=True, null=True)
    image = models.ImageField(upload_to='orders/images/%Y/%m/%d/', null=True, blank=True)
    image_url = models.URLField(null=True, blank=True)  # Original image URL

    def __str__(self):
        return f"{self.product_name} - {self.sku}"

    class Meta:
        ordering = ['id']  # PDF'deki sıraya göre sıralama
