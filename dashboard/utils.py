import os
import PyPDF2
import re
from datetime import datetime
from django.conf import settings
import json
import requests
from urllib.parse import urlparse
from pathlib import Path

def extract_product_name(text_before_sku):
    """Extract product name"""
    try:
        # Split text before SKU into lines and clean empty lines
        lines = [line.strip() for line in text_before_sku.split('\n') if line.strip()]
        
        # Clean special characters and unnecessary spaces
        filtered_lines = []
        for line in lines:
            # Check special cases and skip these lines
            if any(skip in line.lower() for skip in [
                'ship to', 'order date', 'tracking', 'quantity:', 
                'size / style:', 'color:', 'scheduled to ship by',
                'shop', 'payment method', 'shipping method', 'packaging'
            ]):
                continue
            filtered_lines.append(line)
        
        # Get the longest line (usually product name is the longest description)
        if filtered_lines:
            return max(filtered_lines, key=len)
        raise ValueError("Product name not found")
    except Exception as e:
        print(f"Product name extraction error: {str(e)}")
        raise

def extract_image_url(order_text, sku):
    """Extract product image URL"""
    try:
        # Check text before and after SKU
        sku_index = order_text.find(f"SKU: {sku}")
        if sku_index == -1:
            raise ValueError(f"SKU not found: {sku}")
            
        # Get 500 characters before and after SKU
        start_index = max(0, sku_index - 500)
        end_index = min(len(order_text), sku_index + 500)
        search_text = order_text[start_index:end_index]
        
        # Search for Etsy's image URL patterns
        patterns = [
            r'https://i\.etsystatic\.com/\d+/r/il/[a-zA-Z0-9]+/\d+/il_\d+x\d+\.\d+\.jpg',
            r'https://i\.etsystatic\.com/\d+/\d+/\d+/il_\d+xN\.\d+\.jpg',
            r'https://i\.etsystatic\.com/[a-zA-Z0-9]+/[a-zA-Z0-9]+/[a-zA-Z0-9]+/il_fullxfull\.\d+\.jpg'
        ]
        
        for pattern in patterns:
            url_match = re.search(pattern, search_text)
            if url_match:
                return url_match.group(0)
        
        raise ValueError("Product image not found")
    except Exception as e:
        print(f"Image URL extraction error for SKU {sku}: {str(e)}")
        raise

def save_product_image(image_url, order_id, sku):
    """Ürün görselini indir ve kaydet"""
    try:
        if not image_url:
            return ''
            
        # Dosya adını oluştur
        file_name = f"{order_id}_{sku}.jpg"
        relative_path = os.path.join('orders', 'images', str(order_id), file_name)
        absolute_path = os.path.join(settings.MEDIA_ROOT, relative_path)
        
        # Dizin yapısını oluştur
        os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
        
        # Görseli indir
        response = requests.get(image_url)
        if response.status_code == 200:
            with open(absolute_path, 'wb') as f:
                f.write(response.content)
            return relative_path
            
        return ''
    except Exception as e:
        print(f"Image save error: {str(e)}")
        return ''

def get_search_patterns(pattern_type):
    """Get active search patterns from database"""
    from .models import SearchPattern
    patterns = SearchPattern.objects.filter(pattern_type=pattern_type, is_active=True)
    return [pattern.pattern for pattern in patterns]

def extract_items(order_text, order_id):
    """Extract product information"""
    try:
        items = []
        # Split all text into lines
        lines = order_text.split('\n')
        current_item = None
        
        # Get search patterns
        size_patterns = get_search_patterns('size')
        color_patterns = get_search_patterns('color')
        
        # Add default patterns if none exist
        if not size_patterns:
            size_patterns = ['Size', 'Style', 'Size / Style']
        if not color_patterns:
            color_patterns = ['Color']
        
        for i, line in enumerate(lines):
            if line.startswith('SKU:'):
                if current_item:
                    items.append(current_item)
                
                # Start new item
                sku_match = re.search(r'SKU: (.*)', line)
                if not sku_match or not sku_match.group(1).strip():
                    raise ValueError("SKU value not found")
                
                current_item = {
                    'sku': sku_match.group(1).strip(),
                    'errors': []  # List to hold error messages
                }
                continue
            
            if current_item is None:
                continue
                
            if 'Quantity:' in line:
                qty_match = re.search(r'Quantity: (\d+)', line)
                if not qty_match:
                    current_item['errors'].append("Quantity not found")
                else:
                    try:
                        current_item['quantity'] = int(qty_match.group(1))
                    except ValueError:
                        current_item['errors'].append("Quantity is not a valid number")
                continue
            
            # Check for size using patterns
            size_found = False
            for pattern in size_patterns:
                if pattern in line:
                    size_match = re.search(f"{pattern}.*?:\s*(.*?)(?=\n|$)", line, re.IGNORECASE)
                    if size_match and size_match.group(1).strip():
                        current_item['size'] = size_match.group(1).strip()
                        size_found = True
                        break
            if not size_found and any(pattern in line for pattern in size_patterns):
                current_item['errors'].append("Size/Style not found")
            
            # Check for color using patterns
            color_found = False
            for pattern in color_patterns:
                if pattern in line:
                    color_match = re.search(f"{pattern}.*?:\s*(.*?)(?=\n|$)", line, re.IGNORECASE)
                    if color_match and color_match.group(1).strip():
                        current_item['color'] = color_match.group(1).strip()
                        color_found = True
                        break
            if not color_found and any(pattern in line for pattern in color_patterns):
                current_item['errors'].append("Color not found")

            if 'Personalization:' in line or 'Personalization' in line:
                # Önce "Personalization:" formatını dene
                personalization_match = re.search(r'Personalization:\s*(.*?)(?=\n|$)', line)
                if not personalization_match:
                    # Eğer bulunamazsa "Personalization" formatını dene
                    personalization_match = re.search(r'Personalization\s*(.*?)(?=\n|$)', line)
                
                if personalization_match and personalization_match.group(1).strip():
                    current_item['personalization'] = personalization_match.group(1).strip()
                continue
        
        # Process last item
        if current_item:
            items.append(current_item)
        
        # Make sure there is at least one item
        if not items:
            raise ValueError(f"No products found for order {order_id}")
            
        return items
    except Exception as e:
        print(f"Items extraction error for order {order_id}: {str(e)}")
        print(f"Order text: {order_text[:200]}...")  # Show first 200 characters
        raise

def extract_images_from_page(page, batch_id):
    """PDF sayfasından resimleri çıkar ve kaydet"""
    try:
        images = []
        if '/Resources' in page and '/XObject' in page['/Resources']:
            xObject = page['/Resources']['/XObject'].get_object()
            
            image_count = 1
            for obj in xObject:
                if xObject[obj]['/Subtype'] == '/Image':
                    try:
                        # Resim verilerini al
                        image_data = xObject[obj].get_object()
                        
                        # Resim formatını belirle
                        if xObject[obj]['/Filter'] == '/DCTDecode':
                            extension = '.jpg'
                        elif xObject[obj]['/Filter'] == '/FlateDecode':
                            extension = '.png'
                        elif xObject[obj]['/Filter'] == '/JPXDecode':
                            extension = '.jp2'
                        else:
                            print(f"Desteklenmeyen resim formatı: {xObject[obj]['/Filter']}")
                            continue
                        
                        # Tüm resimleri jpg olarak kaydet
                        extension = '.jpg'
                        
                        # Yeni dosya adı formatı: media/orders/images/batch_id/1.jpg
                        relative_path = os.path.join('orders', 'images', str(batch_id), f'{image_count}{extension}')
                        absolute_path = os.path.join(settings.MEDIA_ROOT, relative_path)
                        
                        # Dizin yapısını oluştur
                        os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
                        
                        # Resmi kaydet
                        image_data = image_data.get_data()
                        with open(absolute_path, 'wb') as img_file:
                            img_file.write(image_data)
                        
                        images.append(relative_path)
                        image_count += 1
                        
                    except Exception as e:
                        print(f"Resim kaydetme hatası: {str(e)}")
                        continue
        
        return images
    except Exception as e:
        print(f"Resim çıkarma hatası: {str(e)}")
        return []

def extract_order_data(pdf_file):
    """Extract order data from PDF"""
    try:
        print(f"Starting PDF extraction. Input type: {type(pdf_file)}")  # Debug için input tipini yazdır
        
        # Read PDF
        reader = None
        try:
            if isinstance(pdf_file, str):
                print(f"Reading PDF from path: {pdf_file}")  # Debug için dosya yolunu yazdır
                reader = PyPDF2.PdfReader(pdf_file, strict=False)
            else:
                print("Reading PDF from file object")  # Debug için dosya objesi olduğunu yazdır
                reader = PyPDF2.PdfReader(pdf_file.file, strict=False)
                
            print(f"PDF reader created successfully")  # Debug için reader oluşturulduğunu yazdır
            
        except Exception as e:
            print(f"PDF reading error: {str(e)}")
            raise Exception("Could not read PDF file. Please upload a valid PDF file.")

        if not reader or len(reader.pages) == 0:
            raise Exception("PDF file is empty or unreadable.")

        # Process pages in chunks
        orders = []
        current_text = ""
        current_order_number = None
        total_pages = len(reader.pages)
        print(f"Processing {total_pages} pages")

        for page_num in range(total_pages):
            try:
                page = reader.pages[page_num]
                if not page:
                    print(f"Page {page_num + 1} could not be read, skipping")
                    continue

                try:
                    page_text = page.extract_text()
                    if not page_text:
                        print(f"No text could be extracted from page {page_num + 1}, skipping")
                        continue
                    
                    # Sayfadaki sipariş numarasını bul
                    order_match = re.search(r'Order #(\d+)', page_text)
                    if order_match:
                        page_order_number = order_match.group(1)
                        
                        # Eğer yeni bir sipariş başladıysa, önceki siparişi işle
                        if current_order_number and current_order_number != page_order_number:
                            # Önceki siparişi işle
                            process_order_text = current_text
                            current_text = page_text
                            
                            try:
                                order_data = process_order_text_to_data(process_order_text)
                                if order_data:
                                    orders.append(order_data)
                            except Exception as e:
                                print(f"Order processing error: {str(e)}")
                            
                            # Yeni sipariş için hazırlık
                            current_order_number = page_order_number
                        else:
                            # Aynı siparişin devamı
                            current_text += page_text
                            if not current_order_number:
                                current_order_number = page_order_number
                    else:
                        # Sipariş numarası yoksa mevcut metne ekle
                        current_text += page_text
                    
                except Exception as e:
                    print(f"Text extraction error for page {page_num + 1}: {str(e)}")
                    continue

            except Exception as e:
                print(f"Page {page_num + 1} processing error: {str(e)}")
                continue

        # Son siparişi işle
        if current_text:
            try:
                order_data = process_order_text_to_data(current_text)
                if order_data:
                    orders.append(order_data)
            except Exception as e:
                print(f"Order processing error: {str(e)}")

        if not orders:
            raise Exception("No order data could be extracted from PDF.")

        print(f"Total {len(orders)} orders processed successfully")
        return orders
    
    except Exception as e:
        error_msg = f"PDF processing error: {str(e)}"
        print(error_msg)
        raise Exception(error_msg)
    
    finally:
        # Clean up memory
        if 'reader' in locals() and reader:
            reader = None

def process_order_text_to_data(order_text):
    """Sipariş metnini işleyip veri yapısına dönüştür"""
    try:
        # Extract basic order information
        order_match = re.search(r'Order #(\d+)', order_text)
        customer_match = re.search(r'Ship to\n(.*?)\n', order_text)
        date_match = re.search(r'Order date\n(.*?)\n', order_text)
        tracking_match = re.search(r'Tracking\n(\d+)\nvia USPS', order_text)
        
        if not all([order_match, customer_match, date_match]):
            print("Missing order information, skipping")
            return None
        
        order_number = order_match.group(1)
        print(f"Processing order: {order_number}")

        try:
            order_date = datetime.strptime(date_match.group(1).strip(), '%b %d, %Y').date()
        except ValueError as e:
            print(f"Date conversion error: {str(e)}")
            return None

        # Create order data
        order_data = {
            'order_number': order_number,
            'customer_name': customer_match.group(1).strip(),
            'shipping_address': extract_address(order_text),
            'order_date': order_date,
            'tracking_number': tracking_match.group(1) if tracking_match else '',
        }

        # Extract products
        try:
            items = extract_items(order_text, order_number)
            if not items:
                print(f"No products found for order {order_number}")
                return None
            order_data['items'] = items
        except Exception as e:
            print(f"Product extraction error: {str(e)}")
            return None
        
        # Add gift message (if exists)
        try:
            gift_message_match = re.search(r'Gift message\n(.*?)\n', order_text)
            if gift_message_match:
                order_data['gift_message'] = gift_message_match.group(1).strip()
        except Exception as e:
            print(f"Gift message extraction error: {str(e)}")
        
        return order_data
    
    except Exception as e:
        print(f"Order text processing error: {str(e)}")
        return None

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