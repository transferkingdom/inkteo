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
from .utils import generate_order_id, extract_order_data
from django.core.serializers.json import DjangoJSONEncoder
from datetime import date, datetime, timedelta
import shutil
from requests_oauthlib import OAuth2Session
import dropbox
import requests
from urllib.parse import urlencode
from django.urls import reverse
import io

# Configure logging
logger = logging.getLogger('dashboard')

# Remove manual log configuration since it's handled in settings.py
try:
    # Create log directory if it doesn't exist
    log_dir = os.path.join('/etc/easypanel/projects/inkteo/inkteo/volumes/logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
        os.chmod(log_dir, 0o755)
        
    # Create log file if it doesn't exist
    log_file = os.path.join(log_dir, 'django.log')
    if not os.path.exists(log_file):
        open(log_file, 'a').close()
        os.chmod(log_file, 0o644)
except Exception as e:
    print(f"Error configuring logger: {str(e)}")

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
    """PDF upload view"""
    if request.method == 'POST':
        if 'pdf_file' not in request.FILES:
            return JsonResponse({
                'status': 'error',
                'message': 'No PDF file uploaded'
            }, status=400)

        try:
            pdf_file = request.FILES['pdf_file']
            
            if not pdf_file.name.endswith('.pdf'):
                return JsonResponse({
                    'status': 'error',
                    'message': 'File must be a PDF'
                }, status=400)

            # Create new batch order
            batch = BatchOrder.objects.create(
                order_id=generate_order_id(),
                status='processing'
            )

            try:
                # PDF dosyasını kaydet
                pdf_path = os.path.join('orders', 'pdfs', str(batch.order_id), pdf_file.name)
                full_path = os.path.join(django_settings.MEDIA_ROOT, pdf_path)
                
                # Dizin yapısını oluştur
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                
                # Dosyayı kaydet
                with open(full_path, 'wb+') as destination:
                    for chunk in pdf_file.chunks():
                        destination.write(chunk)
                
                # PDF dosya yolunu BatchOrder'a kaydet
                batch.pdf_file = pdf_path
                batch.save()

                # PDF'i işle
                orders_data = extract_order_data(full_path)
                
                # Save raw data
                serializable_data = []
                for order in orders_data:
                    order_copy = order.copy()
                    if isinstance(order_copy['order_date'], (date, datetime)):
                        order_copy['order_date'] = order_copy['order_date'].isoformat()
                    serializable_data.append(order_copy)

                batch.raw_data = json.dumps(serializable_data, cls=DjangoJSONEncoder)
                batch.total_orders = len(orders_data)
                batch.save()
                
                # Process orders
                total_items = 0
                processed_skus = set()  # İşlenmiş SKU'ları takip etmek için

                for order_data in orders_data:
                    # Create order
                    order_fields = {
                        'batch': batch,
                        'etsy_order_number': order_data['order_number'],
                        'customer_name': order_data['customer_name'],
                        'shipping_address': order_data['shipping_address'],
                        'order_date': order_data['order_date']
                    }
                    
                    if 'tracking_number' in order_data:
                        order_fields['tracking_number'] = order_data['tracking_number']
                        
                    order = OrderDetail.objects.create(**order_fields)
                    
                    # Process items
                    for item in order_data['items']:
                        # Create item
                        item_fields = {
                            'order': order,
                            'sku': item['sku']
                        }
                        
                        if 'name' in item:
                            item_fields['name'] = item['name']
                        if 'quantity' in item:
                            item_fields['quantity'] = item['quantity']
                            total_items += item['quantity']
                        if 'size' in item:
                            item_fields['size'] = item['size']
                        if 'color' in item:
                            item_fields['color'] = item['color']
                        if 'personalization' in item:
                            item_fields['personalization'] = item['personalization']
                        if 'image_url' in item:
                            item_fields['image_url'] = item['image_url']
                        if 'image' in item and item['image']:
                            item_fields['image'] = item['image']
                            
                        OrderItem.objects.create(**item_fields)
                        processed_skus.add(item['sku'])  # SKU'yu işlenmiş olarak işaretle

                batch.total_items = total_items
                batch.status = 'completed'
                batch.save()

                # Dropbox'tan resimleri indir
                settings = PrintImageSettings.objects.filter(user=request.user).first()
                if settings and settings.use_dropbox:
                    if not settings.dropbox_access_token:
                        return JsonResponse({
                            'status': 'warning',
                            'message': 'PDF uploaded successfully but no Dropbox connection found. Please check your Dropbox connection in Settings.'
                        })
                    
                    try:
                        # Dropbox client oluştur
                        dbx = dropbox.Dropbox(settings.dropbox_access_token)
                        
                        # Her bir benzersiz SKU için resim indir
                        for sku in processed_skus:
                            # Dropbox'ta resmi ara
                            dropbox_path = find_dropbox_image(dbx, sku)
                            if dropbox_path:
                                # Hedef dosya yolunu oluştur
                                filename = os.path.basename(dropbox_path)
                                target_path = os.path.join(
                                    django_settings.MEDIA_ROOT,
                                    'orders',
                                    'images',
                                    str(batch.order_id),
                                    filename
                                )
                                
                                # Resmi indir
                                if download_dropbox_image(dbx, dropbox_path, target_path):
                                    # Veritabanını güncelle - aynı SKU'ya sahip tüm öğeler için
                                    relative_path = os.path.join(
                                        'orders',
                                        'images',
                                        str(batch.order_id),
                                        filename
                                    )
                                    OrderItem.objects.filter(
                                        order__batch=batch,
                                        sku=sku
                                    ).update(print_image=relative_path)
                                    
                                    logger.info(f"Print image downloaded for SKU {sku}: {filename}")
                    
                    except dropbox.exceptions.AuthError:
                        logger.error("Dropbox authentication error")
                        return JsonResponse({
                            'status': 'warning',
                            'message': 'PDF uploaded successfully but there was an error with Dropbox connection. Please refresh your Dropbox connection in Settings (Disconnect and connect again).'
                        })
                    except Exception as e:
                        logger.error(f"Dropbox error: {str(e)}")
                        return JsonResponse({
                            'status': 'warning',
                            'message': f'PDF uploaded successfully but there was an error downloading images from Dropbox: {str(e)}'
                        })

                return JsonResponse({'status': 'success'})

            except Exception as e:
                batch.status = 'error'
                batch.save()
                return JsonResponse({
                    'status': 'error',
                    'message': f'Error processing PDF: {str(e)}'
                })

        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'Error uploading file: {str(e)}'
            })

    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=400)

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

def download_dropbox_image(dbx, dropbox_path, local_path):
    """Dropbox'tan resmi indir"""
    try:
        # Hedef klasörü oluştur
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        try:
            # Dosyayı indir
            with open(local_path, 'wb') as f:
                metadata, response = dbx.files_download(dropbox_path)
                f.write(response.content)
            
            # Dosya izinlerini ayarla
            os.chmod(local_path, 0o644)
            
            logger.info(f"Successfully downloaded image from Dropbox: {dropbox_path}")
            return True
            
        except dropbox.exceptions.AuthError:
            # Token süresi dolmuşsa yenilemeyi dene
            settings = PrintImageSettings.objects.first()
            if not settings or not settings.dropbox_refresh_token:
                logger.error("No refresh token available. Please reconnect to Dropbox.")
                return False
                
            if refresh_dropbox_token(settings):
                # Yeni token ile yeni bir Dropbox client oluştur
                dbx = dropbox.Dropbox(settings.dropbox_access_token)
                # İndirmeyi tekrar dene
                with open(local_path, 'wb') as f:
                    metadata, response = dbx.files_download(dropbox_path)
                    f.write(response.content)
                
                # Dosya izinlerini ayarla
                os.chmod(local_path, 0o644)
                
                logger.info(f"Successfully downloaded image from Dropbox after token refresh: {dropbox_path}")
                return True
            else:
                logger.error("Failed to refresh token. Please reconnect to Dropbox.")
                return False
        
    except Exception as e:
        logger.error(f"Dropbox download error for {dropbox_path}: {str(e)}")
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
                                # Dropbox'ta resmi ara
                                dropbox_path = find_dropbox_image(dbx, item.sku)
                                if dropbox_path:
                                    # Hedef dosya yolunu oluştur
                                    filename = os.path.basename(dropbox_path)
                                    target_path = os.path.join(
                                        django_settings.MEDIA_ROOT,
                                        'orders',
                                        'images',
                                        str(batch.order_id),
                                        filename
                                    )
                                    
                                    # Resmi indir
                                    if download_dropbox_image(dbx, dropbox_path, target_path):
                                        # Veritabanını güncelle
                                        relative_path = os.path.join(
                                            'orders',
                                            'images',
                                            str(batch.order_id),
                                            filename
                                        )
                                        item.print_image = relative_path
                                        item.save()
                                        
                                        logger.info(f"Print image downloaded for SKU {item.sku}: {filename}")
                    
                except dropbox.exceptions.AuthError:
                    logger.error("Dropbox authentication error")
                    messages.warning(request, "There was an error with Dropbox connection. Please refresh your Dropbox connection in Settings (Disconnect and connect again).")
                except Exception as e:
                    logger.error(f"Dropbox error: {str(e)}")
                    messages.warning(request, f"There was an error downloading images from Dropbox: {str(e)}")
        
        return render(request, 'dashboard/orders/detail.html', {
            'batch': batch,
            'active_tab': 'orders'
        })
        
    except Exception as e:
        logger.error(f"Error in order detail: {str(e)}")
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
    # Yetkilendirme URL'sini oluştur
    params = {
        'client_id': django_settings.DROPBOX_APP_KEY,
        'response_type': 'code',
        'redirect_uri': django_settings.DROPBOX_OAUTH_CALLBACK_URL,
        'token_access_type': 'offline'
    }
    
    authorization_url = f"https://www.dropbox.com/oauth2/authorize?{urlencode(params)}"
    
    return redirect(authorization_url)

def dropbox_callback(request):
    """Process Dropbox OAuth2 callback"""
    try:
        # Token alma isteği için parametreler
        data = {
            'code': request.GET.get('code'),
            'grant_type': 'authorization_code',
            'client_id': django_settings.DROPBOX_APP_KEY,
            'client_secret': django_settings.DROPBOX_APP_SECRET,
            'redirect_uri': django_settings.DROPBOX_OAUTH_CALLBACK_URL
        }
        
        # Token alma isteği
        response = requests.post('https://api.dropboxapi.com/oauth2/token', data=data)
        
        if response.status_code == 200:
            token_data = response.json()
            
            # Save token information
            settings, _ = PrintImageSettings.objects.get_or_create(user=request.user)
            settings.dropbox_access_token = token_data.get('access_token')
            settings.dropbox_refresh_token = token_data.get('refresh_token')
            settings.dropbox_token_expiry = datetime.now() + timedelta(seconds=token_data.get('expires_in', 14400))
            settings.use_dropbox = True
            settings.save()
            
            logger.info("Successfully connected to Dropbox")
            messages.success(request, 'Successfully connected to Dropbox.')
        else:
            logger.error(f"Failed to get token: {response.text}")
            messages.error(request, 'Failed to connect to Dropbox.')
        
    except Exception as e:
        logger.error(f"Dropbox OAuth error: {str(e)}")
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
        
        messages.success(request, 'Successfully disconnected from Dropbox.')
        
    except PrintImageSettings.DoesNotExist:
        messages.error(request, 'Print settings not found.')
    except Exception as e:
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