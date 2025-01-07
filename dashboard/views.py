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
from datetime import date, datetime
import shutil

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
        print_settings = None
    
    context = {
        'print_settings': print_settings
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
    
    # Test Docker volume permissions
    try:
        print("\n[DEBUG] ===== DOCKER VOLUME CHECK =====")
        media_root = django_settings.MEDIA_ROOT
        print(f"[DEBUG] MEDIA_ROOT: {media_root}")
        print(f"[DEBUG] MEDIA_ROOT exists: {os.path.exists(media_root)}")
        if os.path.exists(media_root):
            print(f"[DEBUG] MEDIA_ROOT permissions: {oct(os.stat(media_root).st_mode)[-3:]}")
            print(f"[DEBUG] MEDIA_ROOT contents: {os.listdir(media_root)}")
        
        orders_dir = os.path.join(media_root, 'orders')
        print(f"[DEBUG] Orders directory: {orders_dir}")
        print(f"[DEBUG] Orders directory exists: {os.path.exists(orders_dir)}")
        if os.path.exists(orders_dir):
            print(f"[DEBUG] Orders directory permissions: {oct(os.stat(orders_dir).st_mode)[-3:]}")
            print(f"[DEBUG] Orders directory contents: {os.listdir(orders_dir)}")
        
        images_dir = os.path.join(orders_dir, 'images')
        print(f"[DEBUG] Images directory: {images_dir}")
        print(f"[DEBUG] Images directory exists: {os.path.exists(images_dir)}")
        if os.path.exists(images_dir):
            print(f"[DEBUG] Images directory permissions: {oct(os.stat(images_dir).st_mode)[-3:]}")
            print(f"[DEBUG] Images directory contents: {os.listdir(images_dir)}")
    except Exception as e:
        print(f"[ERROR] Error checking Docker volume: {str(e)}")
        print(f"[ERROR] Full traceback: {traceback.format_exc()}")
    
    # Get print folder path from settings
    try:
        print("\n[DEBUG] ===== PRINT FOLDER CHECK =====")
        print_settings = PrintImageSettings.objects.get(user=request.user)
        print_folder = print_settings.print_folder_path
        
        print(f"[DEBUG] Print folder path: {print_folder}")
        if not print_folder:
            print("[WARNING] Print folder path is empty!")
            return render(request, 'dashboard/orders/detail.html', {'batch': batch, 'active_tab': 'orders'})
        
        if not os.path.exists(print_folder):
            print(f"[WARNING] Print folder does not exist: {print_folder}")
            return render(request, 'dashboard/orders/detail.html', {'batch': batch, 'active_tab': 'orders'})
        
        print("[DEBUG] Print folder exists")
        print(f"[DEBUG] Print folder permissions: {oct(os.stat(print_folder).st_mode)[-3:]}")
        print(f"[DEBUG] Print folder contents: {os.listdir(print_folder)}")
        
        # Create a set to track processed SKUs
        processed_skus = set()
        
        print("\n[DEBUG] ===== PROCESSING ORDERS =====")
        # First, find all unique SKUs that need processing
        for order in batch.orders.all():
            print(f"\n[DEBUG] Processing order: {order.etsy_order_number}")
            for item in order.items.all():
                print(f"\n[DEBUG] Checking item SKU: {item.sku}")
                
                if item.print_image:
                    print(f"[DEBUG] Item already has print image: {item.print_image}")
                    continue
                    
                if item.sku in processed_skus:
                    print(f"[DEBUG] SKU already processed: {item.sku}")
                    continue
                    
                processed_skus.add(item.sku)
                print(f"[DEBUG] Looking for print image for SKU: {item.sku}")
                
                # Search in print folder and subfolders
                found_match = False
                for root, dirs, files in os.walk(print_folder):
                    print(f"\n[DEBUG] Searching in directory: {root}")
                    print(f"[DEBUG] Files in directory: {files}")
                    
                    for file in files:
                        if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                            file_name = os.path.splitext(file)[0].lower()
                            search_sku = item.sku.lower().strip()
                            
                            print(f"[DEBUG] Comparing file: {file_name} with SKU: {search_sku}")
                            
                            # Check if file name matches SKU
                            if search_sku == file_name or file_name.startswith(f"{search_sku}-"):
                                found_match = True
                                source_path = os.path.join(root, file)
                                file_extension = os.path.splitext(file)[1]
                                target_filename = f"{item.sku}{file_extension}"
                                
                                print(f"\n[DEBUG] ===== FOUND MATCHING FILE =====")
                                print(f"[DEBUG] Source path: {source_path}")
                                print(f"[DEBUG] File exists: {os.path.exists(source_path)}")
                                if os.path.exists(source_path):
                                    print(f"[DEBUG] File size: {os.path.getsize(source_path)} bytes")
                                    print(f"[DEBUG] File permissions: {oct(os.stat(source_path).st_mode)[-3:]}")
                                    print(f"[DEBUG] File owner: {os.stat(source_path).st_uid}")
                                    print(f"[DEBUG] File group: {os.stat(source_path).st_gid}")
                                
                                # Create target directory structure
                                target_dir = os.path.join(django_settings.MEDIA_ROOT, 'orders', 'images', str(batch.order_id), 'print_images')
                                try:
                                    print(f"\n[DEBUG] ===== CREATING DIRECTORIES =====")
                                    print(f"[DEBUG] Target directory: {target_dir}")
                                    
                                    # Önce üst dizinleri oluştur
                                    parent_dir = os.path.dirname(target_dir)
                                    print(f"[DEBUG] Creating parent directory: {parent_dir}")
                                    os.makedirs(parent_dir, exist_ok=True)
                                    os.chmod(parent_dir, 0o755)
                                    print(f"[DEBUG] Parent directory created and permissions set")
                                    
                                    # Sonra hedef dizini oluştur
                                    print(f"[DEBUG] Creating target directory: {target_dir}")
                                    os.makedirs(target_dir, exist_ok=True)
                                    os.chmod(target_dir, 0o755)
                                    print(f"[DEBUG] Target directory created and permissions set")
                                    
                                    # Print directory contents and permissions
                                    print(f"[DEBUG] Target directory permissions: {oct(os.stat(target_dir).st_mode)[-3:]}")
                                    print(f"[DEBUG] Target directory owner: {os.stat(target_dir).st_uid}")
                                    print(f"[DEBUG] Target directory group: {os.stat(target_dir).st_gid}")
                                    print(f"[DEBUG] Directory contents: {os.listdir(target_dir) if os.path.exists(target_dir) else 'Directory not found'}")
                                    
                                except Exception as e:
                                    print(f"[ERROR] Error creating directory {target_dir}: {str(e)}")
                                    print(f"[ERROR] Full traceback: {traceback.format_exc()}")
                                    continue
                                
                                # Copy file to target directory
                                target_path = os.path.join(target_dir, target_filename)
                                try:
                                    print(f"\n[DEBUG] ===== COPYING FILE =====")
                                    print(f"[DEBUG] Source: {source_path}")
                                    print(f"[DEBUG] Target: {target_path}")
                                    
                                    # Dosyayı kopyala
                                    try:
                                        with open(source_path, 'rb') as src:
                                            file_data = src.read()
                                            print(f"[DEBUG] Successfully read {len(file_data)} bytes from source file")
                                            
                                            with open(target_path, 'wb') as dst:
                                                dst.write(file_data)
                                                dst.flush()
                                                os.fsync(dst.fileno())  # Ensure data is written to disk
                                                print(f"[DEBUG] Successfully wrote {len(file_data)} bytes to target file")
                                    except IOError as e:
                                        print(f"[ERROR] IOError during file copy: {str(e)}")
                                        print(f"[ERROR] Full traceback: {traceback.format_exc()}")
                                        continue
                                    
                                    # İzinleri ayarla
                                    try:
                                        os.chmod(target_path, 0o644)
                                        print(f"[DEBUG] File permissions set to 644")
                                    except Exception as e:
                                        print(f"[ERROR] Error setting file permissions: {str(e)}")
                                    
                                    # Verify file exists and check its properties
                                    if os.path.exists(target_path):
                                        print(f"[DEBUG] File exists at target path: {target_path}")
                                        print(f"[DEBUG] File size: {os.path.getsize(target_path)} bytes")
                                        print(f"[DEBUG] File permissions: {oct(os.stat(target_path).st_mode)[-3:]}")
                                        print(f"[DEBUG] File owner: {os.stat(target_path).st_uid}")
                                        print(f"[DEBUG] File group: {os.stat(target_path).st_gid}")
                                        
                                        # Set relative path for database
                                        relative_path = os.path.join('orders', 'images', str(batch.order_id), 'print_images', target_filename)
                                        print(f"\n[DEBUG] ===== UPDATING DATABASE =====")
                                        print(f"[DEBUG] Setting database path: {relative_path}")
                                        
                                        # Update all items with the same SKU
                                        same_sku_items = OrderItem.objects.filter(
                                            order__batch=batch,
                                            sku=item.sku
                                        )
                                        for same_item in same_sku_items:
                                            same_item.print_image = relative_path
                                            same_item.save()
                                            print(f"[DEBUG] Updated item {same_item.id} with path: {relative_path}")
                                    else:
                                        print(f"[ERROR] File not found at target path after copy: {target_path}")
                                    
                                except Exception as e:
                                    print(f"[ERROR] Error copying file {source_path} to {target_path}: {str(e)}")
                                    print(f"[ERROR] Full traceback: {traceback.format_exc()}")
                                    continue
                                
                                break
                    
                    if found_match:
                        break
                
                if not found_match:
                    print(f"[WARNING] No matching file found for SKU: {item.sku}")
                
    except PrintImageSettings.DoesNotExist:
        print("[WARNING] PrintImageSettings not found")
        pass
    except Exception as e:
        print(f"[ERROR] Error searching print images: {str(e)}")
        print(f"[ERROR] Full traceback: {traceback.format_exc()}")
    
    context = {
        'batch': batch,
        'active_tab': 'orders'
    }
    return render(request, 'dashboard/orders/detail.html', context)

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

def find_print_image(sku):
    """SKU'ya göre print image dosyasını bul"""
    settings = PrintImageSettings.objects.first()
    if not settings or not settings.print_folder_path:
        return None
        
    for root, dirs, files in os.walk(settings.print_folder_path):
        for file in files:
            if sku in file:
                return os.path.join(root, file)
    return None