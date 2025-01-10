from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from accounts.forms import UserProfileForm, CompanyForm
from accounts.models import Company
from allauth.account.models import EmailAddress, EmailConfirmation
from allauth.account.adapter import get_adapter
from django.contrib.auth import logout, get_user_model
from django.views.decorators.csrf import ensure_csrf_cookie
import logging
import traceback
from django.http import HttpResponse, JsonResponse
import json
from django.utils import timezone
from django.conf import settings as django_settings
import os
from allauth.account.utils import send_email_confirmation
from django.db.models import Q
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import BatchOrder, OrderDetail, OrderItem, PrintImageSettings
from .utils import (
    generate_order_id, extract_order_data, process_image_for_print,
    check_sku_image_exists, find_dropbox_image, download_dropbox_image,
    refresh_dropbox_token, process_pdf_file, create_qr_code
)
import dropbox
import requests
from urllib.parse import urlencode
from datetime import datetime, timedelta
import re
from PIL import Image

# Configure logging
logger = logging.getLogger('dashboard')

User = get_user_model()

@login_required
def home(request):
    # Total orders sayısını al
    total_orders = OrderDetail.objects.count()
    
    context = {
        'total_orders': total_orders,
        'active_tab': 'home'
    }
    return render(request, 'dashboard/home.html', context)

@ensure_csrf_cookie
@login_required
def settings_view(request):
    # Clear any existing messages
    from django.contrib.messages import get_messages
    storage = get_messages(request)
    for message in storage:
        pass  # This will clear all messages
    
    # Clear session messages
    if 'messages' in request.session:
        del request.session['messages']
    
    # Get print settings
    try:
        print_settings = PrintImageSettings.objects.get(user=request.user)
    except PrintImageSettings.DoesNotExist:
        print_settings = PrintImageSettings.objects.create(user=request.user)
    
    context = {
        'print_settings': print_settings,
        'active_tab': 'settings'
    }
    
    return render(request, 'dashboard/settings.html', context)

@ensure_csrf_cookie
@login_required
def update_profile(request):
    if request.method == 'POST':
        try:
            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name')
            new_email = request.POST.get('email')
            
            user = request.user
            
            print(f"DEBUG: Current email: {user.email}")
            print(f"DEBUG: New email: {new_email}")
            
            # Update name
            user.first_name = first_name
            user.last_name = last_name
            
            # Check email change
            if new_email and new_email != user.email:
                try:
                    # Check if email is already in use by another user
                    if EmailAddress.objects.filter(email=new_email).exclude(user=user).exists():
                        return JsonResponse({
                            'success': False,
                            'message': 'This email address is already in use.'
                        })
                    
                    print("DEBUG: Starting email update process")
                    
                    # Store old email for rollback
                    old_email = user.email
                    
                    try:
                        # 1. Delete any existing unverified emails
                        EmailAddress.objects.filter(user=user, verified=False).delete()
                        print("DEBUG: Deleted unverified emails")
                        
                        # 2. Set all existing email addresses to non-primary
                        EmailAddress.objects.filter(user=user).update(primary=False)
                        print("DEBUG: Set existing emails to non-primary")
                        
                        # 3. Create new email address first
                        email_address = EmailAddress.objects.create(
                            user=user,
                            email=new_email,
                            primary=True,
                            verified=False
                        )
                        print("DEBUG: Created new email address")
                        
                        # 4. Update user's email after creating EmailAddress
                        user.email = new_email
                        user.save()
                        print("DEBUG: User email updated")
                        
                        # 5. Create email confirmation
                        from allauth.account.models import EmailConfirmation
                        confirmation = EmailConfirmation.create(email_address)
                        confirmation.sent = timezone.now()
                        confirmation.save()
                        print("DEBUG: Created email confirmation")
                        
                        # 6. Send verification email
                        from django.core.mail import send_mail
                        from django.template.loader import render_to_string
                        from django.urls import reverse
                        
                        # Get the site URL
                        site_url = f"https://{request.get_host()}"
                        
                        context = {
                            'user': user,
                            'activate_url': f"{site_url}/accounts/confirm-email/{confirmation.key}",
                            'current_site': request.get_host(),
                            'key': confirmation.key,
                        }
                        
                        subject = 'Please Confirm Your Email'
                        message = render_to_string('account/email/email_confirmation_message.txt', context)
                        html_message = render_to_string('account/email/email_confirmation_message.html', context)
                        
                        send_mail(
                            subject,
                            message,
                            None,  # From email (will use DEFAULT_FROM_EMAIL)
                            [new_email],
                            html_message=html_message,
                            fail_silently=False,
                        )
                        print("DEBUG: Sent verification email")
                        
                        # Logout user
                        logout(request)
                        
                        return JsonResponse({
                            'success': True,
                            'message': 'Email updated successfully. You will be logged out in 10 seconds. '
                                     'Please check your inbox and verify your new email before logging in again.',
                            'redirect': '/accounts/login/'
                        })
                        
                    except Exception as e:
                        print(f"DEBUG: Inner error: {str(e)}")
                        # Rollback if error occurs
                        if 'old_email' in locals():
                            user.email = old_email
                            user.save()
                        EmailAddress.objects.filter(user=user, email=new_email).delete()
                        raise
                    
                except Exception as e:
                    print(f"DEBUG: Error in email update process: {str(e)}")
                    return JsonResponse({
                        'success': False,
                        'message': f'Error updating email: {str(e)}'
                    })
            
            else:
                # Save if only name is changed
                user.save()
                return JsonResponse({
                    'success': True,
                    'message': 'Your profile has been updated successfully.',
                    'redirect': None
                })
            
        except Exception as e:
            print(f"DEBUG: Error in profile update: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': f'An error occurred: {str(e)}'
            })
    
    return redirect('dashboard:settings')

@login_required
def update_company(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        tax_id = request.POST.get('tax_id')
        address = request.POST.get('address')
        
        try:
            # Get or create company for user
            company, created = Company.objects.get_or_create(user=request.user)
            
            # Update company details
            company.name = name
            company.tax_id = tax_id
            company.address = address
            company.save()
            
            messages.success(request, 'Company details updated successfully.')
            
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
            
        return redirect('dashboard:settings')
    
    return redirect('dashboard:settings')

@ensure_csrf_cookie
@login_required
def change_password(request):
    if request.method == 'POST':
        try:
            current_password = request.POST.get('current_password')
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')
            
            user = request.user
            
            print(f"DEBUG: Starting password change for user: {user.email}")
            
            # Check current password
            if not user.check_password(current_password):
                return JsonResponse({
                    'success': False,
                    'current_password_error': 'Current password is incorrect'
                })
            
            # Check if passwords match
            if new_password != confirm_password:
                return JsonResponse({
                    'success': False,
                    'new_password_error': 'Passwords do not match'
                })
            
            # Validate password
            try:
                validate_password(new_password, user)
            except ValidationError as e:
                return JsonResponse({
                    'success': False,
                    'new_password_error': e.messages[0]
                })
            
            # Change password
            user.set_password(new_password)
            user.save()
            
            print("DEBUG: Password changed successfully")
            
            # Logout user
            logout(request)
            
            return JsonResponse({
                'success': True,
                'message': 'Password changed successfully. You will be logged out in 10 seconds. '
                         'Please login with your new password.',
                'redirect': '/accounts/login/'
            })
            
        except Exception as e:
            print(f"DEBUG: Error in password change: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': f'An error occurred: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
def orders(request):
    """Orders ana sayfası"""
    batches = BatchOrder.objects.all()
    context = {
        'batches': batches,
        'active_tab': 'orders'
    }
    return render(request, 'dashboard/orders/list.html', context)

@login_required
def upload_orders(request):
    if request.method == 'POST':
        try:
            # PDF dosyasını al
            pdf_file = request.FILES.get('pdf_file')
            if not pdf_file:
                return JsonResponse({
                    'status': 'error',
                    'message': 'No PDF file uploaded'
                })
            
            # Batch order oluştur
            batch = BatchOrder.objects.create(
                user=request.user,
                pdf_file=pdf_file,
                status='processing'
            )
            
            try:
                # PDF'den siparişleri çıkar
                orders = extract_order_data(pdf_file)
                if not orders:
                    batch.status = 'error'
                    batch.save()
                    return JsonResponse({
                        'status': 'error',
                        'message': 'No orders found in PDF'
                    })
                
                # İşlenen SKU'ları takip et
                processed_skus = set()
                total_items = 0
                
                # Her sipariş için
                for order in orders:
                    # OrderDetail oluştur
                    order_detail = OrderDetail.objects.create(
                        batch=batch,
                        customer_name=order.get('customer_name', ''),
                        shipping_address=order.get('shipping_address', ''),
                        order_date=order.get('order_date'),
                        etsy_order_number=order.get('order_number', ''),
                        shipping_method=order.get('shipping_method', 'Standard'),
                        tracking_number=order.get('tracking_number', ''),
                        total_items=len(order.get('items', []))
                    )
                    
                    # Her ürün için
                    for item in order.get('items', []):
                        sku = item.get('sku', '')
                        if sku:
                            processed_skus.add(sku)
                            
                            # OrderItem oluştur
                            OrderItem.objects.create(
                                order=order_detail,
                                sku=sku,
                                name=item.get('name', ''),
                                quantity=item.get('quantity', 1),
                                size=item.get('size', ''),
                                color=item.get('color', ''),
                                personalization=item.get('personalization', '')
                            )
                            total_items += 1
                
                # Batch'i güncelle
                batch.total_orders = len(orders)
                batch.total_items = total_items
                batch.status = 'completed'
                batch.save()
                
                # Dropbox'tan resimleri indir
                settings = PrintImageSettings.objects.filter(user=request.user).first()
                if settings and settings.use_dropbox and settings.dropbox_access_token:
                    print("Dropbox settings found and enabled")
                    try:
                        # Dropbox client oluştur
                        dbx = dropbox.Dropbox(settings.dropbox_access_token)
                        print("Dropbox client created")
                        
                        # Her bir benzersiz SKU için resim indir
                        for sku in processed_skus:
                            print(f"Processing SKU: {sku}")
                            
                            # 1. ÖNCE SKU folder'da ara
                            sku_exists, batch_exists, sku_path, batch_path = check_sku_image_exists(sku, batch.order_id)
                            print(f"Image check results - SKU exists: {sku_exists}, Batch exists: {batch_exists}")
                            
                            # 2. SKU folder'da yoksa, Dropbox'tan indir
                            if not sku_exists:
                                print(f"SKU image does not exist in SKU folder, searching in Dropbox")
                                # Dropbox'ta tam eşleşme ara
                                dropbox_path = find_dropbox_image(dbx, sku)
                                if dropbox_path:
                                    print(f"Found exact matching image in Dropbox: {dropbox_path}")
                                    # Resmi indir ve işle
                                    if download_dropbox_image(dbx, dropbox_path, f"{sku}.png", batch.order_id):
                                        print(f"Successfully downloaded and processed image for SKU: {sku}")
                                        # Veritabanını güncelle
                                        relative_path = os.path.join(
                                            'orders',
                                            'images',
                                            str(batch.order_id),
                                            f"{sku}.png"
                                        )
                                        OrderItem.objects.filter(
                                            order__batch=batch,
                                            sku=sku
                                        ).update(print_image=relative_path)
                                    else:
                                        print(f"Failed to download/process image for SKU: {sku}")
                                else:
                                    print(f"No exact matching image found in Dropbox for SKU: {sku}")
                            else:
                                print(f"SKU image already exists at {sku_path}")
                                # Batch klasörü için resmi işle
                                if not batch_exists:
                                    print(f"Processing existing image for batch {batch.order_id}")
                                    batch_path = os.path.join(django_settings.MEDIA_ROOT, 'orders', 'images', str(batch.order_id), f"{sku}.png")
                                    if process_image_for_print(sku_path, batch_path):
                                        print(f"Successfully processed image for batch {batch.order_id}, SKU {sku}")
                                        # Veritabanını güncelle
                                        relative_path = os.path.join(
                                            'orders',
                                            'images',
                                            str(batch.order_id),
                                            f"{sku}.png"
                                        )
                                        OrderItem.objects.filter(
                                            order__batch=batch,
                                            sku=sku
                                        ).update(print_image=relative_path)
                                    else:
                                        print(f"Failed to process image for batch {batch.order_id}, SKU {sku}")
                                    
                    except dropbox.exceptions.AuthError:
                        print("Dropbox authentication error")
                        return JsonResponse({
                            'status': 'warning',
                            'message': 'PDF uploaded successfully but there was an error with Dropbox connection. Please refresh your Dropbox connection in Settings (Disconnect and connect again).'
                        })
                    except Exception as e:
                        print(f"Dropbox error: {str(e)}")
                        print(f"Error details: {traceback.format_exc()}")
                        return JsonResponse({
                            'status': 'warning',
                            'message': f'PDF uploaded successfully but there was an error downloading images from Dropbox: {str(e)}'
                        })
                else:
                    print("Dropbox settings not found or not enabled")
                
                return JsonResponse({'status': 'success'})
                
            except Exception as e:
                batch.status = 'error'
                batch.save()
                print(f"Error processing PDF: {str(e)}")
                print(f"Error details: {traceback.format_exc()}")
                return JsonResponse({
                    'status': 'error',
                    'message': f'Error processing PDF: {str(e)}'
                })
                
        except Exception as e:
            print(f"Error uploading file: {str(e)}")
            print(f"Error details: {traceback.format_exc()}")
            return JsonResponse({
                'status': 'error',
                'message': f'Error uploading file: {str(e)}'
            })
            
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    })

def refresh_dropbox_token(settings):
    """Dropbox access token'ı yenile"""
    try:
        if not settings.dropbox_refresh_token:
            logger.error("No refresh token available")
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
            logger.info("Dropbox token refreshed successfully")
            return True
        else:
            logger.error(f"Failed to refresh token: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error refreshing Dropbox token: {str(e)}")
        return False

def find_dropbox_image(dbx, sku):
    """Dropbox'ta SKU'ya göre resim dosyası arama"""
    try:
        # SKU'yu küçük harfe çevir
        sku_lower = sku.lower()
        
        try:
            # Dropbox'ta arama yap
            search_results = dbx.files_search('', sku_lower)
            
            # Sonuçları kontrol et
            for match in search_results.matches:
                if isinstance(match.metadata, dropbox.files.FileMetadata):
                    filename = match.metadata.name.lower()
                    # Dosya adında SKU varsa ve .png uzantılıysa
                    if sku_lower in filename and filename.endswith('.png'):
                        return match.metadata.path_display
            
            return None
            
        except dropbox.exceptions.AuthError:
            # Token süresi dolmuşsa yenilemeyi dene
            settings = PrintImageSettings.objects.first()
            if refresh_dropbox_token(settings):
                # Yeni token ile yeni bir Dropbox client oluştur
                dbx = dropbox.Dropbox(settings.dropbox_access_token)
                # Aramayı tekrar dene
                search_results = dbx.files_search('', sku_lower)
                
                # Sonuçları kontrol et
                for match in search_results.matches:
                    if isinstance(match.metadata, dropbox.files.FileMetadata):
                        filename = match.metadata.name.lower()
                        # Dosya adında SKU varsa ve .png uzantılıysa
                        if sku_lower in filename and filename.endswith('.png'):
                            return match.metadata.path_display
                
                return None
            else:
                logger.error("Failed to refresh token. Please reconnect to Dropbox.")
                return None
                
    except Exception as e:
        logger.error(f"Dropbox search error for SKU {sku}: {str(e)}")
        return None

def download_dropbox_image(dbx, dropbox_path, local_path, batch_id=None):
    """Dropbox'tan resmi indir ve işle"""
    try:
        # Orijinal SKU'yu al ve küçük harfe çevir
        original_sku = os.path.splitext(os.path.basename(local_path))[0].lower()
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
                
                # Orijinal SKU adıyla kaydet (küçük harfli)
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
            # Batch klasörü için hedef yolu oluştur (küçük harfli SKU adını kullan)
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

@login_required
def order_detail(request, order_id):
    """Order detail view"""
    try:
        batch = get_object_or_404(BatchOrder, order_id=order_id)
        
        # Dropbox bağlantısını kontrol et
        settings = PrintImageSettings.objects.filter(user=request.user).first()
        if settings and settings.use_dropbox:
            if not settings.dropbox_access_token:
                messages.warning(request, "Dropbox connection not found. Please check your Dropbox connection in Settings.")
            else:
                try:
                    # Dropbox client oluştur
                    dbx = dropbox.Dropbox(settings.dropbox_access_token)
                    
                    # Her bir sipariş öğesi için işlem yap
                    for order in batch.orders.all():
                        for item in order.items.all():
                            if not item.print_image:  # Eğer print_image henüz ayarlanmamışsa
                                # Önce SKU ile aynı isimde dosya var mı kontrol et
                                batch_folder = os.path.join(django_settings.MEDIA_ROOT, 'orders', 'images', str(batch.order_id))
                                if os.path.exists(batch_folder):
                                    # Klasördeki tüm dosyaları listele
                                    files = os.listdir(batch_folder)
                                    # SKU'yu büyük/küçük harf duyarsız ara
                                    sku_found = False
                                    for file in files:
                                        if file.lower().startswith(item.sku.lower()) and file.lower().endswith('.png'):
                                            # Dosya bulundu, relative path'i güncelle
                                            relative_path = os.path.join('orders', 'images', str(batch.order_id), file)
                                            item.print_image = relative_path
                                            item.save()
                                            sku_found = True
                                            print(f"Found existing image for SKU {item.sku}: {file}")
                                            break
                                    
                                    if not sku_found:
                                        # Dropbox'ta resmi ara
                                        dropbox_path = find_dropbox_image(dbx, item.sku)
                                        if dropbox_path:
                                            # Resmi indir ve işle
                                            if download_dropbox_image(dbx, dropbox_path, None, batch.order_id):
                                                # Veritabanını güncelle
                                                relative_path = os.path.join(
                                                    'orders',
                                                    'images',
                                                    str(batch.order_id),
                                                    f"{item.sku}.png"
                                                )
                                                item.print_image = relative_path
                                                item.save()
                                                print(f"Print image downloaded and processed for SKU {item.sku}")
                    
                except dropbox.exceptions.AuthError:
                    print("Dropbox authentication error")
                    messages.warning(request, "There was an error with Dropbox connection. Please refresh your Dropbox connection in Settings (Disconnect and connect again).")
                except Exception as e:
                    print(f"Dropbox error: {str(e)}")
                    print(f"Error details: {traceback.format_exc()}")
                    messages.warning(request, f"There was an error downloading images from Dropbox: {str(e)}")
        
        # QR kodları kontrol et ve eksik olanları oluştur
        for order in batch.orders.all():
            if not order.qr_code_url:
                qr_code_url = create_qr_code(batch.order_id, order.etsy_order_number)
                if qr_code_url:
                    order.qr_code_url = qr_code_url
                    order.save()
                    print(f"QR kod oluşturuldu ve kaydedildi: {qr_code_url}")
                else:
                    print(f"QR kod oluşturulamadı: {order.etsy_order_number}")
        
        return render(request, 'dashboard/orders/detail.html', {
            'batch': batch,
            'active_tab': 'orders'
        })
        
    except Exception as e:
        print(f"Error in order detail: {str(e)}")
        print(f"Error details: {traceback.format_exc()}")
        messages.error(request, "Error loading order details.")
        return redirect('dashboard:orders')

@login_required
def print_image_settings(request):
    if request.method == 'POST':
        try:
            use_dropbox = request.POST.get('use_dropbox') == 'on'
            
            # Get or create print settings
            settings, created = PrintImageSettings.objects.get_or_create(
                user=request.user,
                defaults={'use_dropbox': use_dropbox}
            )
            
            if not created:
                settings.use_dropbox = use_dropbox
                settings.save()
            
            return JsonResponse({
                'status': 'success',
                'message': 'Settings saved successfully'
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
    
    # GET request - return current settings
    try:
        settings = PrintImageSettings.objects.get(user=request.user)
        return JsonResponse({
            'status': 'success',
            'use_dropbox': settings.use_dropbox
        })
    except PrintImageSettings.DoesNotExist:
        return JsonResponse({
            'status': 'success',
            'use_dropbox': False
        })

def find_print_image(sku):
    """Find print image file by SKU"""
    settings = PrintImageSettings.objects.first()
    if not settings or not settings.use_dropbox:
        return None
        
    try:
        # Dropbox client oluştur
        dbx = dropbox.Dropbox(settings.dropbox_access_token)
        return find_dropbox_image(dbx, sku)
    except Exception as e:
        logger.error(f"Error finding print image for SKU {sku}: {str(e)}")
        return None

def dropbox_auth(request):
    """Start Dropbox OAuth2 authorization"""
    try:
        # Yetkilendirme URL'sini oluştur
        params = {
            'client_id': django_settings.DROPBOX_APP_KEY,
            'response_type': 'code',
            'redirect_uri': django_settings.DROPBOX_OAUTH_CALLBACK_URL,
            'token_access_type': 'offline'
        }
        
        authorization_url = f"https://www.dropbox.com/oauth2/authorize?{urlencode(params)}"
        print(f"Redirecting to Dropbox auth URL: {authorization_url}")
        
        return redirect(authorization_url)
    except Exception as e:
        print(f"Error in dropbox_auth: {str(e)}")
        print(f"Error details: {traceback.format_exc()}")
        messages.error(request, 'An error occurred while connecting to Dropbox.')
        return redirect('dashboard:settings')

def dropbox_callback(request):
    """Process Dropbox OAuth2 callback"""
    try:
        auth_code = request.GET.get('code')
        if not auth_code:
            print("No auth code received from Dropbox")
            messages.error(request, 'No authorization code received from Dropbox.')
            return redirect('dashboard:settings')
            
        print(f"Received auth code from Dropbox: {auth_code}")
        
        # Token alma isteği için parametreler
        data = {
            'code': auth_code,
            'grant_type': 'authorization_code',
            'client_id': django_settings.DROPBOX_APP_KEY,
            'client_secret': django_settings.DROPBOX_APP_SECRET,
            'redirect_uri': django_settings.DROPBOX_OAUTH_CALLBACK_URL
        }
        
        print("Requesting access token from Dropbox")
        # Token alma isteği
        response = requests.post('https://api.dropboxapi.com/oauth2/token', data=data)
        
        if response.status_code == 200:
            token_data = response.json()
            print("Successfully received token data from Dropbox")
            
            # Save token information
            settings, _ = PrintImageSettings.objects.get_or_create(user=request.user)
            settings.dropbox_access_token = token_data.get('access_token')
            settings.dropbox_refresh_token = token_data.get('refresh_token')
            settings.dropbox_token_expiry = datetime.now() + timedelta(seconds=token_data.get('expires_in', 14400))
            settings.use_dropbox = True
            settings.save()
            
            print("Successfully saved Dropbox token information")
            messages.success(request, 'Successfully connected to Dropbox.')
        else:
            print(f"Failed to get token: {response.text}")
            messages.error(request, 'Failed to connect to Dropbox.')
        
    except Exception as e:
        print(f"Error in dropbox_callback: {str(e)}")
        print(f"Error details: {traceback.format_exc()}")
        messages.error(request, 'An error occurred while connecting to Dropbox.')
    
    return redirect('dashboard:settings')

def dropbox_disconnect(request):
    """Disconnect from Dropbox"""
    try:
        settings = PrintImageSettings.objects.get(user=request.user)
        settings.dropbox_access_token = None
        settings.dropbox_refresh_token = None
        settings.dropbox_token_expiry = None
        settings.use_dropbox = False
        settings.save()
        
        print("Successfully disconnected from Dropbox")
        messages.success(request, 'Successfully disconnected from Dropbox.')
        
    except PrintImageSettings.DoesNotExist:
        print("Print settings not found")
        messages.error(request, 'Print settings not found.')
    except Exception as e:
        print(f"Error disconnecting from Dropbox: {str(e)}")
        print(f"Error details: {traceback.format_exc()}")
        messages.error(request, f'Error disconnecting from Dropbox: {str(e)}')
    
    return redirect('dashboard:settings')

@login_required
def select_print_folder(request):
    """Print klasörü seçimi"""
    if request.method == 'POST':
        folder_path = request.POST.get('folder_path')
        if folder_path:
            settings = PrintImageSettings.objects.first()
            if not settings:
                settings = PrintImageSettings.objects.create()
            settings.print_folder_path = folder_path
            settings.save()
            return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'})

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
        print(f"Extracted shipping address for order {order_number}: {shipping_address}")

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
                
            # SKU'ları küçük harfe çevir
            for item in items:
                if 'sku' in item:
                    item['sku'] = item['sku'].lower()
                    
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

@login_required
def single_order_detail(request, batch_id, etsy_order_number):
    """Single order detail view"""
    try:
        batch = get_object_or_404(BatchOrder, order_id=batch_id)
        order = get_object_or_404(OrderDetail, batch=batch, etsy_order_number=etsy_order_number)
        
        # QR kodu kontrol et ve eksikse oluştur
        if not order.qr_code_url:
            qr_code_url = create_qr_code(batch.order_id, order.etsy_order_number)
            if qr_code_url:
                order.qr_code_url = qr_code_url
                order.save()
                print(f"QR kod oluşturuldu ve kaydedildi: {qr_code_url}")
            else:
                print(f"QR kod oluşturulamadı: {order.etsy_order_number}")
        
        return render(request, 'dashboard/orders/detail.html', {
            'batch': batch,
            'order': order,
            'single_order': True,
            'active_tab': 'orders'
        })
        
    except Exception as e:
        print(f"Error in single order detail: {str(e)}")
        print(f"Error details: {traceback.format_exc()}")
        messages.error(request, "Error loading order details.")
        return redirect('dashboard:orders')

@login_required
def upload_pdf(request):
    """PDF yükleme view'i"""
    if request.method == 'POST' and request.FILES.get('pdf_file'):
        pdf_file = request.FILES['pdf_file']
        
        # PDF dosyasını işle
        batch = process_pdf_file(pdf_file, request)
        
        if batch:
            messages.success(request, 'PDF başarıyla işlendi.')
            return JsonResponse({'status': 'success', 'batch_id': batch.order_id})
        else:
            messages.error(request, 'PDF işlenirken bir hata oluştu.')
            return JsonResponse({'status': 'error'}, status=500)
            
    return redirect('dashboard:orders')

def process_pdf_file(pdf_file, request):
    """
    PDF dosyasını işler ve BatchOrder objesi oluşturur
    """
    try:
        from .models import BatchOrder, OrderDetail
        
        # Yeni batch order oluştur
        batch = BatchOrder.objects.create(
            order_id=generate_order_id(),
            status='processing'
        )
        
        # PDF'den siparişleri çıkar
        orders_data = extract_order_data(pdf_file)
        if not orders_data:
            raise Exception("PDF'den sipariş verisi çıkarılamadı.")
        
        # Her sipariş için Order objesi oluştur
        for order_data in orders_data:
            order = OrderDetail.objects.create(
                batch=batch,
                etsy_order_number=order_data['order_number'],
                customer_name=order_data['customer_name'],
                shipping_address=order_data['shipping_address'],
                order_date=order_data['order_date'],
                tracking_number=order_data.get('tracking_number', '')
            )
            
            # QR kod oluştur
            qr_code_url = create_qr_code(batch.order_id, order.etsy_order_number)
            if qr_code_url:
                order.qr_code_url = qr_code_url
                order.save()
                print(f"QR kod oluşturuldu: {qr_code_url}")
            else:
                print(f"QR kod oluşturulamadı: {order.etsy_order_number}")
        
        # Batch bilgilerini güncelle
        batch.total_orders = len(orders_data)
        batch.total_items = sum(len(order.get('items', [])) for order in orders_data)
        batch.status = 'completed'
        batch.save()
        
        return batch
        
    except Exception as e:
        print(f"Error processing PDF file: {str(e)}")
        if 'batch' in locals():
            batch.status = 'error'
            batch.save()
        return None

def generate_qr_code_view(request, batch_id, order_number):
    """QR kod oluşturma view'i"""
    try:
        # QR kodu oluştur
        qr_code_url = create_qr_code(batch_id, order_number)
        
        if qr_code_url:
            return JsonResponse({'success': True, 'url': qr_code_url})
        else:
            return JsonResponse({'success': False, 'error': 'QR kod oluşturulamadı'})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})