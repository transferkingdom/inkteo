from django.db import models
from django.utils import timezone

class BatchOrder(models.Model):
    """Toplu sipariş yüklemesi için ana model"""
    order_id = models.CharField(max_length=20, unique=True)  # örn: 1000-20240321153000
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
        ordering = ['-order_date']

class OrderItem(models.Model):
    """Siparişlerdeki her bir ürün için model"""
    order = models.ForeignKey(OrderDetail, on_delete=models.CASCADE, related_name='items')
    product_name = models.CharField(max_length=255)
    sku = models.CharField(max_length=50)
    quantity = models.IntegerField(default=1)
    size = models.CharField(max_length=20)
    color = models.CharField(max_length=50)
    image = models.ImageField(upload_to='orders/images/%Y/%m/%d/', null=True, blank=True)
    image_url = models.URLField(null=True, blank=True)  # Orijinal görsel URL'i

    def __str__(self):
        return f"{self.product_name} - {self.sku}"
