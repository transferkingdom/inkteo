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
def order_list(request):
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
    print("Upload orders view called")
    print("Request method:", request.method)
    print("Files:", request.FILES)
    print("POST data:", request.POST)
    print("MEDIA_ROOT:", django_settings.MEDIA_ROOT)  # django_settings kullan

    if request.method == 'POST':
        if 'pdf_file' not in request.FILES:
            print("No PDF file in request")
            return JsonResponse({
                'status': 'error',
                'message': 'No PDF file uploaded'
            }, status=400)

        try:
            pdf_file = request.FILES['pdf_file']
            print(f"Processing file: {pdf_file.name}, size: {pdf_file.size}")
            
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
            print(f"Created batch order: {batch.order_id}")

            try:
                # Önce PDF dosyasını kaydet
                pdf_path = os.path.join('orders', 'pdfs', str(batch.order_id), pdf_file.name)
                full_path = os.path.join(django_settings.MEDIA_ROOT, pdf_path)  # django_settings kullan
                print(f"PDF will be saved to: {full_path}")
                
                # Dizin yapısını oluştur
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                print(f"Directory created: {os.path.dirname(full_path)}")  # Debug için dizin yolunu yazdır
                
                # Dosyayı kaydet
                with open(full_path, 'wb+') as destination:
                    for chunk in pdf_file.chunks():
                        destination.write(chunk)
                print("PDF file saved successfully")  # Debug için kayıt durumunu yazdır
                
                # PDF dosya yolunu BatchOrder'a kaydet
                batch.pdf_file = pdf_path
                batch.save()
                print(f"PDF path saved to batch: {pdf_path}")  # Debug için kaydedilen yolu yazdır

                # Şimdi kaydedilen dosyayı işle
                print(f"Starting PDF processing from: {full_path}")  # Debug için işleme başlangıcını yazdır
                orders_data = extract_order_data(full_path)
                print(f"Extracted {len(orders_data)} orders from PDF")
                
                # Save raw data - convert datetime objects to string
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
                for order_data in orders_data:
                    # Create order with only available fields
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
                        # Create item with only available fields
                        item_fields = {
                            'order': order,
                            'sku': item['sku']  # SKU is required
                        }
                        
                        # Add other fields only if they exist
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

                batch.total_items = total_items
                batch.status = 'completed'
                batch.save()

                return JsonResponse({'status': 'success'})

            except Exception as e:
                print(f"Error processing PDF: {str(e)}")
                batch.status = 'error'
                batch.save()
                return JsonResponse({
                    'status': 'error',
                    'message': f'Error processing PDF: {str(e)}'
                })

        except Exception as e:
            print(f"Error uploading file: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': f'Error uploading file: {str(e)}'
            })

    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=400)

@login_required
def order_detail(request, order_id):
    """Batch detay sayfası"""
    batch = get_object_or_404(BatchOrder, order_id=order_id)
    
    try:
        logger.info("\n========== PRINT IMAGE SEARCH STARTED ==========")
        logger.info(f"Batch ID: {batch.order_id}")
        
        # Her bir sipariş öğesi için print image ara
        for order in batch.orders.all():
            for item in order.items.all():
                if not item.print_image:  # Eğer print image henüz bulunmamışsa
                    logger.info(f"Searching print image for SKU: {item.sku}")
                    
                    # Print image'ı bul (yerel veya Dropbox)
                    image_path = find_print_image(item.sku)
                    
                    if image_path:
                        logger.info(f"Found print image: {image_path}")
                        
                        # Hedef dizin yolu
                        target_dir = os.path.join(django_settings.MEDIA_ROOT, 'orders', 'images', str(batch.order_id), 'print_images')
                        os.makedirs(target_dir, exist_ok=True)
                        
                        # Hedef dosya yolu
                        target_path = os.path.join(target_dir, os.path.basename(image_path))
                        
                        try:
                            # Dosyayı kopyala
                            if not os.path.exists(target_path):
                                shutil.copy2(image_path, target_path)
                                logger.info(f"Copied print image to: {target_path}")
                            
                            # Veritabanında yolu güncelle
                            relative_path = os.path.join('orders', 'images', str(batch.order_id), 'print_images', os.path.basename(image_path))
                            item.print_image = relative_path
                            item.save()
                            logger.info(f"Updated database record with path: {relative_path}")
                            
                        except Exception as e:
                            logger.error(f"Error copying file: {str(e)}")
                    else:
                        logger.warning(f"No print image found for SKU: {item.sku}")
    
    except Exception as e:
        logger.error(f"Error in order detail: {str(e)}")
    
    return render(request, 'dashboard/orders/detail.html', {
        'batch': batch,
        'active_tab': 'orders'
    })

@login_required
def print_image_settings(request):
    if request.method == 'POST':
        try:
            folder_path = request.POST.get('print_folder_path')
            
            # Get or create print settings
            settings, created = PrintImageSettings.objects.get_or_create(
                user=request.user,
                defaults={'print_folder_path': folder_path}
            )
            
            if not created:
                settings.print_folder_path = folder_path
                settings.save()
            
            # Production ortamında Docker volume'da klasör oluştur
            if not django_settings.DEBUG:
                docker_path = os.path.join('/etc/easypanel/projects/inkteo/inkteo/volumes/print_images')
                os.makedirs(docker_path, mode=0o755, exist_ok=True)
                logger.info(f"Created Docker volume directory: {docker_path}")
            
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
            'print_folder_path': settings.print_folder_path
        })
    except PrintImageSettings.DoesNotExist:
        return JsonResponse({
            'status': 'success',
            'print_folder_path': ''
        })

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

def find_print_image_in_dropbox(dbx, sku, folder_path='/Print Images'):
    """Dropbox'ta SKU'ya göre print image dosyasını bul"""
    try:
        # Dropbox klasörünü listele
        result = dbx.files_list_folder(folder_path, recursive=True)
        
        # Dosyaları kontrol et
        while True:
            for entry in result.entries:
                if isinstance(entry, dropbox.files.FileMetadata):
                    if sku.lower() in entry.name.lower():
                        return entry.path_display
            
            # Daha fazla sonuç varsa devam et
            if result.has_more:
                result = dbx.files_list_folder_continue(result.cursor)
            else:
                break
                
        return None
        
    except Exception as e:
        logger.error(f"Dropbox search error: {str(e)}")
        return None

def download_from_dropbox(dbx, dropbox_path, local_path):
    """Dropbox'tan dosyayı indir"""
    try:
        # Dizin yapısını oluştur
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        # Dosyayı indir
        with open(local_path, 'wb') as f:
            metadata, response = dbx.files_download(dropbox_path)
            f.write(response.content)
            
        return True
        
    except Exception as e:
        logger.error(f"Dropbox download error: {str(e)}")
        return False

def find_print_image(sku):
    """SKU'ya göre print image dosyasını bul"""
    try:
        # Önce yerel dizinde ara
        settings = PrintImageSettings.objects.first()
        if settings and settings.print_folder_path:
            for root, dirs, files in os.walk(settings.print_folder_path):
                for file in files:
                    if sku.lower() in file.lower():
                        return os.path.join(root, file)
        
        # Yerel dizinde bulunamazsa ve Dropbox bağlantısı varsa Dropbox'ta ara
        if settings and settings.use_dropbox and settings.dropbox_access_token:
            try:
                # Dropbox client oluştur
                dbx = dropbox.Dropbox(settings.dropbox_access_token)
                
                # Dropbox'ta dosyayı ara
                dropbox_path = find_print_image_in_dropbox(dbx, sku, settings.dropbox_folder_path)
                if dropbox_path:
                    # Yerel kayıt yolu oluştur
                    local_path = os.path.join(django_settings.MEDIA_ROOT, 'orders', 'print_images', os.path.basename(dropbox_path))
                    
                    # Dropbox'tan indir
                    if download_from_dropbox(dbx, dropbox_path, local_path):
                        return local_path
                    
            except Exception as e:
                logger.error(f"Dropbox error: {str(e)}")
        
        return None
        
    except Exception as e:
        logger.error(f"Find print image error: {str(e)}")
        return None

@login_required
def dropbox_auth(request):
    """Dropbox yetkilendirme başlatma view'ı"""
    try:
        # Dropbox OAuth2 flow başlat
        oauth2_session = OAuth2Session(
            django_settings.DROPBOX_APP_KEY,
            redirect_uri=django_settings.DROPBOX_OAUTH_CALLBACK_URL,
            scope=['files.content.read', 'files.content.write']
        )
        
        authorization_url, state = oauth2_session.authorization_url(
            'https://www.dropbox.com/oauth2/authorize'
        )
        
        # State'i session'da sakla
        request.session['dropbox_oauth_state'] = state
        
        return redirect(authorization_url)
        
    except Exception as e:
        messages.error(request, f'Dropbox bağlantısı sırasında bir hata oluştu: {str(e)}')
        return redirect('dashboard:settings')

@login_required
def dropbox_callback(request):
    """Dropbox callback view'ı"""
    try:
        code = request.GET.get('code')
        state = request.GET.get('state')
        stored_state = request.session.get('dropbox_oauth_state')
        
        if not code:
            messages.error(request, 'Dropbox yetkilendirme kodu alınamadı.')
            return redirect('dashboard:settings')
            
        if state != stored_state:
            messages.error(request, 'Güvenlik doğrulaması başarısız oldu.')
            return redirect('dashboard:settings')
            
        # Token al
        oauth2_session = OAuth2Session(
            django_settings.DROPBOX_APP_KEY,
            redirect_uri=django_settings.DROPBOX_OAUTH_CALLBACK_URL
        )
        
        token = oauth2_session.fetch_token(
            'https://api.dropbox.com/oauth2/token',
            client_secret=django_settings.DROPBOX_APP_SECRET,
            code=code
        )
        
        # Token'ı kaydet
        print_settings = PrintImageSettings.objects.get(user=request.user)
        print_settings.dropbox_access_token = token['access_token']
        print_settings.use_dropbox = True
        print_settings.save()
        
        messages.success(request, 'Dropbox bağlantısı başarıyla kuruldu.')
        return redirect('dashboard:settings')
        
    except Exception as e:
        messages.error(request, f'Dropbox bağlantısı sırasında bir hata oluştu: {str(e)}')
        return redirect('dashboard:settings')

@login_required
def dropbox_disconnect(request):
    """Dropbox bağlantısını kesme view'ı"""
    try:
        print_settings = PrintImageSettings.objects.get(user=request.user)
        print_settings.dropbox_access_token = ''
        print_settings.use_dropbox = False
        print_settings.save()
        
        messages.success(request, 'Dropbox bağlantısı başarıyla kesildi.')
    except Exception as e:
        messages.error(request, f'Dropbox bağlantısını keserken bir hata oluştu: {str(e)}')
    
    return redirect('dashboard:settings')