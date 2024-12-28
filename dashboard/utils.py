import os
import PyPDF2
import re
from datetime import datetime
from django.conf import settings
import json

def generate_order_id():
    """Yeni bir batch order ID oluştur"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    
    # Son batch'i bul
    from .models import BatchOrder
    last_batch = BatchOrder.objects.order_by('-order_id').first()
    
    if last_batch:
        try:
            # Son ID'nin ilk 4 rakamını al
            last_id = int(last_batch.order_id.split('-')[0])
            # 1000'den küçükse 1000'den, değilse son ID + 1'den başla
            new_id = max(1000, last_id + 1)
        except (ValueError, IndexError):
            new_id = 1000
    else:
        new_id = 1000
    
    return f"{new_id:04d}-{timestamp}"

def extract_address(order_text):
    """Kargo adresini çıkar"""
    try:
        # Ship to ile başlayan ve başka bir bölüme kadar olan kısmı al
        address_match = re.search(r'Ship to\n(.*?)(?=\n\d+ item|\nScheduled to ship by|\nShop)', 
                                order_text, re.DOTALL)
        if address_match:
            # İlk satırı (müşteri adı) çıkar ve kalan adresi döndür
            address_lines = address_match.group(1).strip().split('\n')[1:]
            return '\n'.join(address_lines)
        return ''
    except Exception as e:
        print(f"Address extraction error: {str(e)}")
        return ''

def extract_date(order_text):
    """Sipariş tarihini çıkar"""
    try:
        date_match = re.search(r'Order date\n(.*?)\n', order_text)
        if date_match:
            date_str = date_match.group(1).strip()
            # Aug 21, 2024 formatını datetime'a çevir
            return datetime.strptime(date_str, '%b %d, %Y').date()
        return None
    except Exception as e:
        print(f"Date extraction error: {str(e)}")
        return None

def extract_tracking(order_text):
    """Takip numarasını çıkar"""
    try:
        tracking_match = re.search(r'Tracking\n(\d+)\nvia USPS', order_text)
        if tracking_match:
            return tracking_match.group(1)
        return ''
    except Exception as e:
        print(f"Tracking extraction error: {str(e)}")
        return ''

def extract_items(order_text):
    """Ürün bilgilerini çıkar"""
    try:
        items = []
        # Ürün bloklarını bul
        product_blocks = re.finditer(
            r'SKU: (.*?)\n'
            r'Quantity: (\d+)\n'
            r'Size / Style: (.*?)\n'
            r'Color: (.*?)\n',
            order_text
        )
        
        for block in product_blocks:
            # Ürün adını bul (SKU'dan önceki satır)
            product_lines = order_text[:block.start()].split('\n')
            product_name = product_lines[-2] if len(product_lines) > 1 else ''
            
            items.append({
                'name': product_name.strip(),
                'sku': block.group(1).strip(),
                'quantity': int(block.group(2)),
                'size': block.group(3).strip(),
                'color': block.group(4).strip(),
                'image_url': ''  # Şimdilik boş, daha sonra eklenecek
            })
        
        return items
    except Exception as e:
        print(f"Items extraction error: {str(e)}")
        return []

def extract_order_data(pdf_file):
    """PDF'den sipariş verilerini çıkar"""
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text()

        # Debug için tüm metni yazdır
        print("Extracted Text:", text)

        # Siparişleri ayır (Order # ile başlayan bölümler)
        orders = re.split(r'(?=Order #\d+)', text)
        orders = [order for order in orders if order.strip().startswith('Order #')]

        parsed_orders = []
        for order in orders:
            try:
                order_data = {
                    'order_number': re.search(r'Order #(\d+)', order).group(1),
                    'customer_name': re.search(r'Ship to\n(.*?)\n', order).group(1),
                    'shipping_address': extract_address(order),
                    'order_date': extract_date(order),
                    'tracking_number': extract_tracking(order),
                    'items': extract_items(order)
                }
                parsed_orders.append(order_data)
            except Exception as e:
                print(f"Error parsing order: {str(e)}")
                continue

        return parsed_orders

    except Exception as e:
        raise Exception(f"PDF parsing error: {str(e)}")

def save_product_image(image_url, order_id):
    """Ürün görselini indir ve kaydet"""
    # Image download and save logic
    pass 