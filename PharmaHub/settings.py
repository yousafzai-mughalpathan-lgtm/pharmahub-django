"""
Django settings for PharmaHub project - UPDATED FOR ADMIN API
Your Original Settings + Admin Panel Integration
"""
import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'False').strip().lower() in {'1', 'true', 'yes', 'on'}

# ============================================
# INSTALLED APPS - UPDATED WITH ADMIN
# ============================================
INSTALLED_APPS = [
    'daphne',          # ✅ Provides the ASGI/websocket-aware `runserver` command
    'channels',        # ✅ WebSocket support — both MUST be before staticfiles so
                       # daphne's runserver wins over staticfiles' plain WSGI one
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    

    # Sites framework (Required for allauth)
    'django.contrib.sites',
    
    # Django Allauth (Keep existing)
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',

    # ✅ Django REST Framework
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_filters',  # ← ADDED for admin filtering
    # Extensions
    'django_extensions',

    # Your apps
    'pharmacy',
    'dashboards',      # ← MUST BE HERE
    'authentication',  # Has CustomUser
    'customers_d',
    'pages',
    'admin_panel',     # ✅ Admin Panel app
    'api',             # ✅ API app
    'orders',          # ✅ Orders app (for admin order management)
]

SITE_ID = 1

# ============================================
# MIDDLEWARE - UPDATED WITH ADMIN MIDDLEWARE
# ============================================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # For API CORS
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    
    # Your existing middleware
    'authentication.middleware.RoleBasedAccessMiddleware',
    
    # ✅ Admin Panel middleware (optional - comment out if causing issues)
    'admin_panel.middleware.SecurityLoggingMiddleware',
    'admin_panel.middleware.ActivityTrackingMiddleware',
    
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'PharmaHub.urls'

# ============================================
# TEMPLATES - UPDATED FOR ADMIN PANEL
# ============================================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',
            BASE_DIR / 'admin_panel' / 'templates',  # ← ADDED for admin templates
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                # Your existing context processors
                'authentication.context_processors.dynamic_base_template',
                'customers_d.context_processors.cart_count',
                'admin_panel.context_processors.admin_notifications', 
                'dashboards.context_processors.pharmacy_context',
                'dashboards.context_processors.pharmacy_data',
                'dashboards.context_processors.pharmacy_notifications',
                'customers_d.context_processors.customer_notif_count',
            ],
        },
    },
]

WSGI_APPLICATION = 'PharmaHub.wsgi.application'

# Use Channels for ASGI
ASGI_APPLICATION = 'PharmaHub.asgi.application'

# Channel layer configuration (in-memory for development)
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer'
    }
}

# ============================================
# # Rate Limiting Settings
# ============================================
RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = 'default'

# Cache Settings 
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'pharmabuild-cache',
    }
}

# ============================================
# CUSTOM USER MODEL - KEEP EXISTING
# ============================================
AUTH_USER_MODEL = 'authentication.CustomUser'

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# ============================================
# AUTHENTICATION BACKENDS - KEEP AS IS
# ============================================
AUTHENTICATION_BACKENDS = [
    'authentication.backends.EmailBackend',
    'authentication.backends.LockoutAwareAllauthBackend',
    #'django.contrib.auth.backends.ModelBackend',
    #'authentication.backends.EmailBackend',

]
# ============================================
# DATABASE - UPDATED FOR SAFE TESTING (Postgres)
# ============================================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'PharmaHub'),
        'USER': os.getenv('DB_USER', 'pharma'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}




# ============================================
# PASSWORD VALIDATORS - KEEP AS IS
# ============================================
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# ============================================
# INTERNATIONALIZATION - KEEP AS IS
# ============================================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ============================================
# STATIC FILES - KEEP AS IS
# ============================================
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ============================================
# MEDIA FILES - KEEP AS IS
# ============================================
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# ============================================
# EMAIL CONFIGURATION - KEEP AS IS
# ============================================
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', f'PharmaHub <{EMAIL_HOST_USER}>')

# ============================================
# ALLAUTH SETTINGS - KEEP AS IS
# ============================================
LOGIN_URL = '/auth/login-signup/'
LOGOUT_REDIRECT_URL = '/auth/login-signup/'
LOGIN_REDIRECT_URL = '/auth/redirect/'

SOCIALACCOUNT_ADAPTER = 'authentication.adapters.CustomSocialAccountAdapter'
SOCIALACCOUNT_STORE_TOKENS = True
SOCIALACCOUNT_AUTO_SIGNUP = True
ACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
ACCOUNT_SIGNUP_REDIRECT_URL = '/auth/redirect/'
SOCIALACCOUNT_LOGIN_ON_GET = True
ACCOUNT_LOGOUT_ON_GET = True
ACCOUNT_EMAIL_VERIFICATION = "none"
SOCIALACCOUNT_QUERY_EMAIL = True

ACCOUNT_LOGIN_METHODS = {'email', 'username'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'username*', 'password1*', 'password2*']
PASSWORD_RESET_TIMEOUT = 9000

# ============================================
# SECURITY SETTINGS - KEEP AS IS
# ============================================
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
    if host.strip()
]

if DEBUG:
    ACCOUNT_DEFAULT_HTTP_PROTOCOL = "http"
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
else:
    ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# ============================================
# GOOGLE OAUTH - KEEP AS IS
# ============================================
GOOGLE_OAUTH2_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_OAUTH2_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
        'APP': {
            'client_id': GOOGLE_OAUTH2_CLIENT_ID,
            'secret': GOOGLE_OAUTH2_CLIENT_SECRET,
            'key': ''
        }
    }
}

# ============================================
# ✅ DJANGO REST FRAMEWORK - UPDATED FOR ADMIN
# ============================================
REST_FRAMEWORK = {
    # Authentication Classes
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    
    # Default Permissions
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    
    # Pagination
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
    
    # ✅ Filtering - UPDATED with DjangoFilterBackend
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',  # ← ADDED
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    
    # Renderer Classes
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    
    # Parser Classes
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ],
}

# ============================================
# JWT CONFIGURATION - KEEP AS IS
# ============================================
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    
    'JTI_CLAIM': 'jti',
}

# ============================================
# CORS CONFIGURATION - KEEP AS IS
# ============================================
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8080",
    "http://localhost:4200",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8080",
]

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# ============================================
# LOGGING CONFIGURATION - KEEP AS IS
# ============================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        # Autoreload restarts kill in-flight requests; Daphne logs a
        # "took too long to shut down and was killed" warning for this —
        # it's expected noise during dev reloads, not a real error, so
        # we drop just that one message from the console.
        'suppress_daphne_shutdown_noise': {
            '()': 'django.utils.log.CallbackFilter',
            'callback': lambda record: 'took too long to shut down' not in record.getMessage(),
        },
    },
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs/django_errors.log'),
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'filters': ['suppress_daphne_shutdown_noise'],
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'ERROR',
            'propagate': True,
        },
        'admin_panel': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'daphne.server': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# Create logs directory
os.makedirs(os.path.join(BASE_DIR, 'logs'), exist_ok=True)

# ============================================
# ✅ SESSION CONFIGURATION (Added for Admin)
# ============================================
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True

# ============================================
# ✅ CSRF CONFIGURATION (Added for Admin)
# ============================================
CSRF_COOKIE_HTTPONLY = True
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        'CSRF_TRUSTED_ORIGINS',
        'http://localhost:8000,http://127.0.0.1:8000',
    ).split(',')
    if origin.strip()
]


if DEBUG:
    ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'http'


SOCIALACCOUNT_QUERY_PARAMETERS = {
    'prompt': 'select_account',
    'approval_prompt': 'force',
    'access_type': 'offline',
}
