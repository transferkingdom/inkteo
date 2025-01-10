import os
import PyPDF2
import re
from datetime import datetime, timedelta
from django.conf import settings as django_settings
import json
import requests
from urllib.parse import urlparse
from pathlib import Path
from PIL import Image
import dropbox
import logging
from .models import PrintImageSettings
import traceback
import qrcode
import qrcode.constants

# Logger configuration
logger = logging.getLogger('dashboard')

def refresh_dropbox_token(settings):
    """Dropbox access token'ı yenile"""
    try:
        if not settings.dropbox_refresh_token:
            print("No refresh token available")
            return False

        # Token yenileme için gerekli parametreler
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': settings.dropbox_refresh_token,
            'client_id': django_settings.DROPBOX_APP_KEY,
            'client_secret': django_settings.DROPBOX_APP_SECRET
        }

        # Token yenileme isteği
        response = requests.post('https://api.dropboxapi.com/oauth2/token', data=data)
        
        if response.status_code == 200:
            token_data = response.json()
            settings.dropbox_access_token = token_data.get('access_token')
            settings.dropbox_token_expiry = datetime.now() + timedelta(seconds=token_data.get('expires_in', 14400))
            settings.save()
            print("Dropbox token refreshed successfully")
            return True
        else:
            print(f"Failed to refresh token: {response.text}")
            return False
            
    except Exception as e:
        print(f"Error refreshing Dropbox token: {str(e)}")
        return False

# Ensure media directories exist
def ensure_media_directories():
    """Gerekli medya klasörlerinin varlığını kontrol et ve oluştur"""
    try:
        # Ana dizinleri oluştur
        media_dirs = [
            os.path.join(django_settings.MEDIA_ROOT, 'orders'),
            os.path.join(django_settings.MEDIA_ROOT, 'orders', 'skufolder'),
            os.path.join(django_settings.MEDIA_ROOT, 'orders', 'images'),
        ]
        
        for directory in media_dirs:
            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                print(f"Created directory: {directory}")
                try:
                    # Web sunucusu için uygun izinler
                    os.chmod(directory, 0o775)
                    print(f"Set permissions for directory: {directory}")
                except Exception as e:
                    print(f"Warning: Could not set directory permissions: {str(e)}")
                    
            # Dizin varsa bile izinleri kontrol et ve güncelle
            try:
                current_permissions = os.stat(directory).st_mode & 0o777
                if current_permissions != 0o775:
                    os.chmod(directory, 0o775)
                    print(f"Updated permissions for existing directory: {directory}")
            except Exception as e:
                print(f"Warning: Could not update directory permissions: {str(e)}")
                
    except Exception as e:
        print(f"Error creating media directories: {str(e)}")
        print(f"Error details: {traceback.format_exc()}")

# Django başlangıcında dizinleri oluştur
ensure_media_directories()

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
        file_name = f"{order_id}_{sku}.png"  # JPG yerine PNG kullan
        relative_path = os.path.join('orders', 'images', str(order_id), file_name)
        absolute_path = os.path.join(django_settings.MEDIA_ROOT, relative_path)
        
        # Dizin yapısını oluştur
        os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
        print(f"Product image dizini oluşturuldu: {os.path.dirname(absolute_path)}")
        
        # Görseli indir
        response = requests.get(image_url)
        if response.status_code == 200:
            # Önce geçici bir dosyaya kaydet
            temp_path = absolute_path + '.temp'
            with open(temp_path, 'wb') as f:
                f.write(response.content)
            
            # PNG'ye dönüştür ve optimize et
            with Image.open(temp_path) as img:
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                img.save(absolute_path, 'PNG', optimize=True)
            
            # Geçici dosyayı sil
            os.remove(temp_path)
            
            print(f"Product image kaydedildi: {absolute_path}")
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
                        
                        # Yeni dosya adı formatı: orders/images/batch_id/print_images/1.jpg
                        relative_path = os.path.join('orders', 'images', str(batch_id), 'print_images', f'{image_count}{extension}')
                        absolute_path = os.path.join(django_settings.MEDIA_ROOT, relative_path)
                        
                        # Dizin yapısını oluştur
                        target_dir = os.path.dirname(absolute_path)
                        os.makedirs(target_dir, exist_ok=True)
                        print(f"Print image dizini oluşturuldu: {target_dir}")
                        
                        # Set directory permissions
                        try:
                            os.chmod(target_dir, 0o755)
                            print(f"Dizin izinleri ayarlandı: {target_dir}")
                        except Exception as e:
                            print(f"Dizin izinleri ayarlanamadı: {str(e)}")
                        
                        # Resmi kaydet
                        try:
                            image_data = image_data.get_data()
                            with open(absolute_path, 'wb') as img_file:
                                img_file.write(image_data)
                            
                            # Set file permissions
                            os.chmod(absolute_path, 0o644)
                            print(f"Print image kaydedildi ve izinler ayarlandı: {absolute_path}")
                            
                            images.append(relative_path)
                            image_count += 1
                        except Exception as e:
                            print(f"Resim kaydetme veya izin ayarlama hatası: {str(e)}")
                            continue
                        
                    except Exception as e:
                        print(f"Resim işleme hatası: {str(e)}")
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

def extract_address(order_text):
    """Kargo adresini çıkar"""
    try:
        # Ship to ile başlayan ve başka bir bölüme kadar olan kısmı al
        address_match = re.search(r'Ship to\n(.*?)(?=\n\d+ item|\nScheduled to ship by|\nShop|\nOrder date)', 
                                order_text, re.DOTALL)
        
        if address_match:
            # İlk satırı (müşteri adı) çıkar ve kalan adresi döndür
            address_lines = address_match.group(1).strip().split('\n')[1:]
            address = '\n'.join(line.strip() for line in address_lines if line.strip())
            return address
        else:
            print("No address match found in text")
        return ''
    except Exception as e:
        print(f"Address extraction error: {str(e)}")
        return ''

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

        # Adres bilgisini al
        shipping_address = extract_address(order_text)

        # Create order data
        order_data = {
            'order_number': order_number,
            'customer_name': customer_match.group(1).strip(),
            'shipping_address': shipping_address,
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

def process_image_for_print(input_path, output_path, width=500):
    """
    Resmi işleyip belirtilen genişlikte ve orantılı yükseklikte PNG olarak kaydeder.
    """
    try:
        print(f"Processing image from {input_path} to {output_path}")
        
        # Hedef klasörü oluştur
        output_dir = os.path.dirname(output_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            try:
                os.chmod(output_dir, 0o775)
            except Exception as e:
                print(f"Warning: Could not set output directory permissions: {str(e)}")
        print(f"Created/checked directory: {output_dir}")

        # Resmi aç ve işle
        with Image.open(input_path) as img:
            # RGBA moduna çevir (PNG için)
            if img.mode != 'RGBA':
                img = img.convert('RGBA')

            # Orijinal en-boy oranını koru
            aspect_ratio = img.height / img.width
            new_height = int(width * aspect_ratio)
            print(f"Resizing image to {width}x{new_height}")

            # Resmi yeniden boyutlandır
            resized_img = img.resize((width, new_height), Image.Resampling.LANCZOS)

            # Her zaman PNG olarak kaydet
            output_path = os.path.splitext(output_path)[0] + '.png'
            resized_img.save(output_path, 'PNG', optimize=True)
            print(f"Saved processed image as PNG to {output_path}")

            try:
                # Web sunucusu için uygun dosya izinlerini ayarla
                os.chmod(output_path, 0o664)
                print(f"Set permissions for {output_path}")
            except Exception as e:
                print(f"Warning: Could not set file permissions: {str(e)}")

        return True
    except Exception as e:
        print(f"Error processing image: {str(e)}")
        print(f"Error details: {traceback.format_exc()}")
        return False

def check_sku_image_exists(sku, batch_id=None):
    """
    SKU için resmin var olup olmadığını kontrol eder.
    Hem skufolder hem de batch klasöründe kontrol yapar.
    Tam eşleşme yapar (büyük/küçük harf duyarsız).
    """
    try:
        print(f"Checking image existence for SKU: {sku}, Batch ID: {batch_id}")
        
        # SKU folder'daki dosyaları listele
        sku_folder = os.path.join(django_settings.MEDIA_ROOT, 'orders', 'skufolder')
        sku_exists = False
        sku_path = None
        
        if os.path.exists(sku_folder):
            print(f"SKU folder exists: {sku_folder}")
            
            # SKU'yu küçük harfe çevir
            sku_lower = sku.lower()
            
            # Klasördeki tüm dosyaları listele
            try:
                files = os.listdir(sku_folder)
                print(f"Files in SKU folder: {files}")
                
                # Tam eşleşme kontrolü yap
                for file in files:
                    file_name = os.path.splitext(file)[0].lower()
                    if file_name == sku_lower:
                        sku_path = os.path.join(sku_folder, file)
                        if os.path.isfile(sku_path):
                            sku_exists = True
                            print(f"Found matching file: {sku_path}")
                            break
                
                if not sku_exists:
                    print(f"No matching file found for SKU: {sku}")
            except Exception as e:
                print(f"Error listing SKU folder: {str(e)}")
        else:
            print(f"SKU folder does not exist: {sku_folder}")
            # Klasör yoksa oluştur
            try:
                os.makedirs(sku_folder, exist_ok=True)
                os.chmod(sku_folder, 0o775)
                print(f"Created SKU folder: {sku_folder}")
            except Exception as e:
                print(f"Error creating SKU folder: {str(e)}")

        # Eğer batch_id verilmişse, batch klasöründeki işlenmiş resmi de kontrol et
        batch_exists = False
        batch_path = None
        if batch_id:
            batch_folder = os.path.join(django_settings.MEDIA_ROOT, 'orders', 'images', str(batch_id))
            if os.path.exists(batch_folder):
                batch_path = os.path.join(batch_folder, f"{sku}.png")
                batch_exists = os.path.isfile(batch_path)
                print(f"Batch image exists: {batch_exists}" + (f" at {batch_path}" if batch_exists else ""))
            else:
                print(f"Batch folder does not exist: {batch_folder}")
        
        return sku_exists, batch_exists, sku_path, batch_path
        
    except Exception as e:
        print(f"Error checking image existence: {str(e)}")
        print(f"Error details: {traceback.format_exc()}")
        return False, False, None, None

def find_dropbox_image(dbx, sku):
    """Dropbox'ta SKU'ya göre resim dosyası arama (büyük/küçük harf duyarsız tam eşleşme)"""
    try:
        print(f"Searching for SKU in Dropbox: {sku}")
        
        # SKU'yu küçük harfe çevir
        sku_lower = sku.lower()
        
        try:
            # Arama parametrelerini hazırla
            search_args = {
                'query': sku,  # SKU ile ara
                'options': {
                    'file_status': 'active',
                    'filename_only': True,
                    'max_results': 100  # Maksimum sonuç sayısı
                }
            }
            
            print(f"Search query: {search_args['query']}")
            
            # Dropbox API v2 ile arama yap
            result = dbx.files_search_v2(**search_args)
            
            # Tüm sonuçları topla
            all_matches = []
            has_more = True
            
            while has_more:
                if result.matches:
                    print(f"Found {len(result.matches)} matches in current batch")
                    
                    # Mevcut sonuçları işle
                    for match in result.matches:
                        if isinstance(match.metadata, dropbox.files.FileMetadata):
                            file_path = match.metadata.path_display
                            file_name = os.path.splitext(os.path.basename(file_path))[0]
                            file_name_lower = file_name.lower()
                            
                            # Sonucu listeye ekle
                            all_matches.append({
                                'path': file_path,
                                'name': file_name,
                                'name_lower': file_name_lower
                            })
                            print(f"Found match: {file_path} (name: {file_name})")
                
                # Daha fazla sonuç varsa devam et
                if result.has_more:
                    print("Getting more results...")
                    result = dbx.files_search_continue_v2(result.cursor)
                else:
                    has_more = False
            
            print(f"\nTotal matches found: {len(all_matches)}")
            
            # Tüm sonuçları gördükten sonra tam eşleşme kontrolü yap
            print(f"\nChecking {len(all_matches)} matches for exact case-insensitive match...")
            for match in all_matches:
                if match['name_lower'] == sku_lower:
                    print(f"Found exact case-insensitive match: {match['path']}")
                    return match['path']
                else:
                    print(f"Not an exact match: {match['name_lower']} != {sku_lower}")
            
            print(f"No exact case-insensitive match found for SKU: {sku}")
            return None
            
        except dropbox.exceptions.ApiError as e:
            print(f"Dropbox API error: {str(e)}")
            if isinstance(e, dropbox.exceptions.AuthError):
                print("Dropbox authentication error, attempting to refresh token")
                settings = PrintImageSettings.objects.first()
                if refresh_dropbox_token(settings):
                    dbx = dropbox.Dropbox(settings.dropbox_access_token)
                    return find_dropbox_image(dbx, sku)
                else:
                    print("Failed to refresh token")
            return None
                
    except Exception as e:
        print(f"Dropbox search error for SKU {sku}: {str(e)}")
        print(f"Error details: {traceback.format_exc()}")
        return None

def download_dropbox_image(dbx, dropbox_path, local_path, batch_id=None):
    """Dropbox'tan resmi indir ve işle"""
    try:
        # Orijinal SKU'yu al ve büyük harfe çevir
        original_sku = os.path.splitext(os.path.basename(local_path))[0].upper()
        print(f"Processing SKU: {original_sku}")
        
        # 1. ÖNCE SKU folder'da tam eşleşme ara (orijinal SKU ile)
        sku_exists, batch_exists, sku_path, batch_path = check_sku_image_exists(original_sku, batch_id)
        print(f"Image check results - SKU exists: {sku_exists}, Batch exists: {batch_exists}")
        
        # 2. SKU folder'da yoksa, Dropbox'tan indir
        if not sku_exists:
            print(f"SKU image does not exist in SKU folder, searching in Dropbox")
            # Dropbox'ta tam eşleşme ara
            dropbox_path = find_dropbox_image(dbx, original_sku)
            if not dropbox_path:
                print(f"No exact matching image found in Dropbox for SKU: {original_sku}")
                return False
                
            print(f"Found exact matching image in Dropbox: {dropbox_path}")
            
            try:
                # SKU folder için hedef klasörü oluştur ve izinleri ayarla
                sku_folder = os.path.join(django_settings.MEDIA_ROOT, 'orders', 'skufolder')
                if not os.path.exists(sku_folder):
                    os.makedirs(sku_folder, exist_ok=True)
                    try:
                        os.chmod(sku_folder, 0o775)
                    except Exception as e:
                        print(f"Warning: Could not set skufolder permissions: {str(e)}")
                print(f"Created/checked SKU folder: {sku_folder}")
                
                # Orijinal SKU adıyla kaydet (büyük harfle)
                sku_path = os.path.join(sku_folder, f"{original_sku}.png")
                print(f"Downloading to: {sku_path}")
                
                try:
                    # Dropbox'tan indir
                    metadata, response = dbx.files_download(dropbox_path)
                    
                    # Önce geçici dosyaya kaydet
                    temp_path = sku_path + '.temp'
                    with open(temp_path, 'wb') as f:
                        f.write(response.content)
                    
                    try:
                        # Geçici dosya izinlerini ayarla
                        os.chmod(temp_path, 0o664)
                    except Exception as e:
                        print(f"Warning: Could not set temp file permissions: {str(e)}")
                    
                    # PNG'ye dönüştür ve SKU klasörüne kaydet
                    with Image.open(temp_path) as img:
                        if img.mode != 'RGBA':
                            img = img.convert('RGBA')
                        img.save(sku_path, 'PNG', optimize=True)
                    
                    # Geçici dosyayı sil
                    try:
                        os.remove(temp_path)
                    except Exception as e:
                        print(f"Warning: Could not delete temp file: {str(e)}")
                    print(f"Downloaded and converted image to PNG at {sku_path}")
                    
                    try:
                        # Dosya izinlerini web sunucusu için uygun şekilde ayarla
                        os.chmod(sku_path, 0o664)
                        print(f"Set permissions for {sku_path}")
                    except Exception as e:
                        print(f"Warning: Could not set file permissions: {str(e)}")
                        
                    #İndirilen dosyanın varlığını kontrol et
                    if os.path.isfile(sku_path):
                        print(f"Successfully downloaded and saved image to {sku_path}")
                        sku_exists = True
                    else:
                        print(f"Failed to save image to {sku_path}")
                        return False
                    
                except dropbox.exceptions.ApiError as e:
                    print(f"Dropbox API error: {str(e)}")
                    if isinstance(e, dropbox.exceptions.AuthError):
                        print("Dropbox authentication error, attempting to refresh token")
                        settings = PrintImageSettings.objects.first()
                        if refresh_dropbox_token(settings):
                            dbx = dropbox.Dropbox(settings.dropbox_access_token)
                            return download_dropbox_image(dbx, dropbox_path, local_path, batch_id)
                        else:
                            print("Failed to refresh token")
                    return False
                except Exception as e:
                    print(f"Error downloading/saving image: {str(e)}")
                    print(f"Error details: {traceback.format_exc()}")
                    return False
                    
            except Exception as e:
                print(f"Error in SKU folder operations: {str(e)}")
                print(f"Error details: {traceback.format_exc()}")
                return False
        else:
            print(f"SKU image already exists at {sku_path}")
        
        # 3. Batch klasörü için resmi işle (eğer gerekiyorsa)
        if batch_id and not batch_exists and sku_exists:
            print(f"Processing image for batch {batch_id}")
            # Batch klasörü için hedef yolu oluştur (orijinal SKU adını kullan)
            batch_folder = os.path.join(django_settings.MEDIA_ROOT, 'orders', 'images', str(batch_id))
            if not os.path.exists(batch_folder):
                os.makedirs(batch_folder, exist_ok=True)
                try:
                    os.chmod(batch_folder, 0o775)
                except Exception as e:
                    print(f"Warning: Could not set batch folder permissions: {str(e)}")
            
            batch_path = os.path.join(batch_folder, f"{original_sku}.png")
            
            # SKU klasöründeki resmi işle ve batch klasörüne kaydet
            if process_image_for_print(sku_path, batch_path):
                print(f"Successfully processed image for batch {batch_id}, SKU {original_sku}")
                return True
            else:
                print(f"Failed to process image for batch {batch_id}, SKU {original_sku}")
                return False
        
        return True
            
    except Exception as e:
        print(f"Dropbox download error: {str(e)}")
        print(f"Error details: {traceback.format_exc()}")
        return False 

def create_qr_code(batch_id, order_number):
    """
    QR kod oluşturma fonksiyonu
    """
    try:
        print(f"\n=== QR Kod Oluşturuluyor ===")
        print(f"Batch ID: {batch_id}")
        print(f"Order Number: {order_number}")
        
        # QR kod dizini oluştur
        save_dir = os.path.join(django_settings.MEDIA_ROOT, 'orders', 'images', str(batch_id), 'barcodes')
        if not os.path.exists(save_dir):
            os.makedirs(save_dir, exist_ok=True)
            try:
                os.chmod(save_dir, 0o775)
            except Exception as e:
                print(f"Dizin izinleri ayarlanamadı: {str(e)}")
        print(f"QR kod dizini oluşturuldu: {save_dir}")
        
        # QR kod URL'i
        if django_settings.DEBUG:
            base_url = "http://localhost:8000"
        else:
            base_url = "https://orders.inkteo.com"
            
        # URL'nin başına ve sonuna özel karakterler ekle
        url = f"{base_url}/dashboard/orders/{batch_id}/{order_number}"
        formatted_url = f"~{url}\n"  # ~ karakteri başa, \n (Enter) sona eklendi
        print(f"QR kod URL'i: {formatted_url}")
        
        # QR kod oluştur
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(formatted_url)
        qr.make(fit=True)
        
        # QR kod imajı oluştur
        qr_image = qr.make_image(fill_color="black", back_color="white")
        
        # QR kodu kaydet
        image_path = os.path.join(save_dir, f'{order_number}.png')
        qr_image.save(image_path)
        
        try:
            os.chmod(image_path, 0o664)
            print(f"QR kod dosya izinleri ayarlandı: {image_path}")
        except Exception as e:
            print(f"QR kod dosya izinleri ayarlanamadı: {str(e)}")
            
        print(f"QR kod kaydedildi: {image_path}")
        
        # Dosyanın varlığını kontrol et
        if not os.path.exists(image_path):
            print(f"HATA: QR kod dosyası oluşturulamadı: {image_path}")
            return None
            
        # Media URL'i döndür
        media_url = f'/media/orders/images/{batch_id}/barcodes/{order_number}.png'
        print(f"QR kod URL'i: {media_url}")
        print("=== QR Kod Oluşturma Tamamlandı ===\n")
        
        return media_url
        
    except Exception as e:
        print(f"QR kod oluşturma hatası: {str(e)}")
        print(f"Hata detayı: {traceback.format_exc()}")
        return None

def process_pdf_file(pdf_file):
    """
    PDF dosyasını işler ve BatchOrder objesi oluşturur
    """
    try:
        from .models import BatchOrder, OrderDetail, OrderItem
        import traceback
        import os
        
        print("\n=== PDF İşleme Başladı ===")
        
        # Yeni batch order oluştur
        batch = BatchOrder.objects.create(
            order_id=generate_order_id(),
            status='processing'
        )
        print(f"Yeni batch oluşturuldu: {batch.order_id}")
        
        # QR kod dizinini oluştur
        qr_dir = os.path.join(django_settings.MEDIA_ROOT, 'orders', 'images', str(batch.order_id), 'barcodes')
        if not os.path.exists(qr_dir):
            os.makedirs(qr_dir, exist_ok=True)
            try:
                os.chmod(qr_dir, 0o775)
                print(f"QR kod dizini oluşturuldu ve izinler ayarlandı: {qr_dir}")
            except Exception as e:
                print(f"QR kod dizini izinleri ayarlanamadı: {str(e)}")
        
        # PDF'den siparişleri çıkar
        orders_data = extract_order_data(pdf_file)
        if not orders_data:
            raise Exception("PDF'den sipariş verisi çıkarılamadı.")
        
        print(f"Toplam {len(orders_data)} sipariş bulundu")
        
        # Her sipariş için Order objesi oluştur
        for order_data in orders_data:
            print(f"\n--- Sipariş İşleniyor: {order_data['order_number']} ---")
            
            order = OrderDetail.objects.create(
                batch=batch,
                etsy_order_number=order_data['order_number'],
                customer_name=order_data['customer_name'],
                shipping_address=order_data['shipping_address'],
                order_date=order_data['order_date'],
                tracking_number=order_data.get('tracking_number', '')
            )
            print(f"Sipariş detayları kaydedildi")
            
            # QR kod oluştur
            qr_code_url = create_qr_code(batch.order_id, order.etsy_order_number)
            if qr_code_url:
                order.qr_code_url = qr_code_url
                order.save()
                print(f"QR kod oluşturuldu ve kaydedildi: {qr_code_url}")
            else:
                print(f"QR kod oluşturulamadı: {order.etsy_order_number}")
            
            # Sipariş öğelerini kaydet
            for item in order_data.get('items', []):
                OrderItem.objects.create(
                    order=order,
                    sku=item['sku'],
                    quantity=item['quantity']
                )
            print(f"Sipariş öğeleri kaydedildi")
        
        # Batch bilgilerini güncelle
        batch.total_orders = len(orders_data)
        batch.total_items = sum(len(order.get('items', [])) for order in orders_data)
        batch.status = 'completed'
        batch.save()
        print("=== PDF İşleme Tamamlandı ===\n")
        
        return batch
        
    except Exception as e:
        print(f"PDF işleme hatası: {str(e)}")
        print(f"Hata detayı: {traceback.format_exc()}")
        if 'batch' in locals():
            batch.status = 'error'
            batch.save()
        return None 