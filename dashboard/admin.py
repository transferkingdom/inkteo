from django.contrib import admin
from .models import BatchOrder, OrderDetail, OrderItem

@admin.register(BatchOrder)
class BatchOrderAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'upload_date', 'total_orders', 'total_items', 'status')
    list_filter = ('status', 'upload_date')
    search_fields = ('order_id',)
    readonly_fields = ('upload_date',)

@admin.register(OrderDetail)
class OrderDetailAdmin(admin.ModelAdmin):
    list_display = ('etsy_order_number', 'customer_name', 'order_date', 'total_items')
    list_filter = ('order_date',)
    search_fields = ('etsy_order_number', 'customer_name')

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('product_name', 'sku', 'quantity', 'size', 'color')
    list_filter = ('size', 'color')
    search_fields = ('product_name', 'sku')
