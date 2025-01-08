# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'volumes/inkteo-media')

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'volumes/static')

# Serve media files in development
if DEBUG:
    INSTALLED_APPS += ['django.contrib.staticfiles']
    urlpatterns += static(MEDIA_URL, document_root=MEDIA_ROOT) 