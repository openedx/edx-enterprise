"""
These settings are here to use during tests, because django requires them.

In a real-world use case, apps in this project are installed into other
Django applications, so these settings will not be used.
"""

from os.path import abspath, dirname, join

from celery import Celery

from enterprise.constants import (
    ENTERPRISE_ADMIN_ROLE,
    ENTERPRISE_CATALOG_ADMIN_ROLE,
    ENTERPRISE_DASHBOARD_ADMIN_ROLE,
    ENTERPRISE_ENROLLMENT_API_ADMIN_ROLE,
    ENTERPRISE_OPERATOR_ROLE,
)


def here(*args):
    """
    Return the absolute path to a directory from this file.
    """
    return join(abspath(dirname(__file__)), *args)


def root(*args):
    """
    Return the absolute path to some file from the project's root.
    """
    return abspath(join(abspath(here('../..')), *args))


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "default.db",
        "USER": "",
        "PASSWORD": "",
        "HOST": "",
        "PORT": "",
    }
}

INSTALLED_APPS = (
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sites",
    "django.contrib.sessions",
    "django.contrib.admin",  # only used in DEBUG mode
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "waffle",

    "enterprise",
    "consent",
    "integrated_channels.integrated_channel",
    "integrated_channels.cornerstone",
    "integrated_channels.degreed",
    "integrated_channels.canvas",
    "integrated_channels.sap_success_factors",
    "integrated_channels.xapi",
    "edx_rbac",
    "rules.apps.AutodiscoverRulesConfig",
)

MIDDLEWARE_CLASSES = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "crum.CurrentRequestUserMiddleware",
    "waffle.middleware.WaffleMiddleware",
]

MIDDLEWARE = MIDDLEWARE_CLASSES  # Django 1.10 compatibility - the setting was renamed

AUTHENTICATION_BACKENDS = (
    "rules.permissions.ObjectPermissionBackend",
    "django.contrib.auth.backends.ModelBackend",
)

SITE_NAME = 'localhost:18000/'

SESSION_ENGINE = "django.contrib.sessions.backends.file"

LOCALE_PATHS = [
    root("enterprise", "conf", "locale"),
]

MAKO_TEMPLATES = {
    "main": []
}

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": {
                "django.contrib.auth.context_processors.auth",  # this is required for admin
                "django.contrib.messages.context_processors.messages",
            }
        }
    },
]

REPO_ROOT = root('enterprise')

STATIC_ROOT = root('enterprise/assets')

STATIC_URL = '/enterprise/static/'

PLATFORM_NAME = "Test platform"
PLATFORM_DESCRIPTION = "Test description"

ROOT_URLCONF = "enterprise.urls"

SECRET_KEY = "insecure-secret-key"

# Default Site id
SITE_ID = 1

EDX_API_KEY = "PUT_YOUR_API_KEY_HERE"

COURSE_CATALOG_URL_ROOT = "http://localhost:18381/"
COURSE_CATALOG_API_URL = "http://localhost:18381/api/v1/"

LMS_ROOT_URL = "http://lms.example.com"
LMS_INTERNAL_ROOT_URL = "http://localhost:8000"
LMS_ENROLLMENT_API_PATH = "/api/enrollment/v1/"
ECOMMERCE_PUBLIC_URL_ROOT = "http://localhost:18130"
ENTERPRISE_CATALOG_INTERNAL_ROOT_URL = "http://localhost:18160"

ENTERPRISE_ENROLLMENT_API_URL = LMS_INTERNAL_ROOT_URL + LMS_ENROLLMENT_API_PATH

ENTERPRISE_LEARNER_PORTAL_BASE_URL = 'http://localhost:8734'

ENTERPRISE_PUBLIC_ENROLLMENT_API_URL = ENTERPRISE_ENROLLMENT_API_URL

ENTERPRISE_API_CACHE_TIMEOUT = 60

ENTERPRISE_SUPPORT_URL = "http://foo"

ENTERPRISE_TAGLINE = "High-quality online learning opportunities from the world's best universities"

OAUTH_ID_TOKEN_EXPIRATION = 60*60  # in seconds

EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

DEFAULT_FROM_EMAIL = 'course_staff@example.com'

USER_THROTTLE_RATE = '190/minute'
SERVICE_USER_THROTTLE_RATE = '200/minute'
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
    'URL_FORMAT_OVERRIDE': None,
    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.UserRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'user': USER_THROTTLE_RATE,
        'service_user': SERVICE_USER_THROTTLE_RATE,
    },
    'DATETIME_FORMAT': '%Y-%m-%dT%H:%M:%SZ',
}

# URL for the server that django client listens to by default.
TEST_SERVER = "http://testserver"
ALLOWED_HOSTS = ["testserver.enterprise"]
MEDIA_URL = "/"

ECOMMERCE_SERVICE_WORKER_USERNAME = 'ecommerce_worker'
ENTERPRISE_SERVICE_WORKER_USERNAME = 'enterprise_worker'

ENTERPRISE_CUSTOMER_LOGO_IMAGE_SIZE = 512   # Enterprise logo image size limit in KB's

ENTERPRISE_COURSE_ENROLLMENT_AUDIT_MODES = ['audit', 'honor']

# These are standard regexes for pulling out info like course_ids, usage_ids, etc.
COURSE_KEY_PATTERN = r'(?P<course_key_string>[^/+]+(/|\+)[^/+]+(/|\+)[^/?]+)'
COURSE_ID_PATTERN = COURSE_KEY_PATTERN.replace('course_key_string', 'course_id')

USE_TZ = True

MKTG_URLS = {}

ENTERPRISE_CUSTOMER_CATALOG_DEFAULT_CONTENT_FILTER = {
    'content_type': 'course',
    'partner': 'edx',
    'level_type': [
        'Introductory',
        'Intermediate',
        'Advanced'
    ],
    'availability': [
        'Current',
        'Starting Soon',
        'Upcoming'
    ],
    'status': 'published'
}

# For testing edx-rbac rules. This is not the actual value of the setting in prod.
SYSTEM_TO_FEATURE_ROLE_MAPPING = {
    ENTERPRISE_ADMIN_ROLE: [
        ENTERPRISE_DASHBOARD_ADMIN_ROLE,
        ENTERPRISE_CATALOG_ADMIN_ROLE,
        ENTERPRISE_ENROLLMENT_API_ADMIN_ROLE
    ],
    ENTERPRISE_OPERATOR_ROLE: [
        ENTERPRISE_DASHBOARD_ADMIN_ROLE,
        ENTERPRISE_CATALOG_ADMIN_ROLE,
        ENTERPRISE_ENROLLMENT_API_ADMIN_ROLE
    ],
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'rules': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

################################### TRACKING ###################################

LMS_SEGMENT_KEY = 'SOME_KEY'
EVENT_TRACKING_ENABLED = True
EVENT_TRACKING_BACKENDS = {
    'segmentio': {
        'ENGINE': 'eventtracking.backends.routing.RoutingBackend',
        'OPTIONS': {
            'backends': {
                'segment': {'ENGINE': 'eventtracking.backends.segment.SegmentBackend'}
            },
            'processors': [
                {
                    'ENGINE': 'eventtracking.processors.whitelist.NameWhitelistProcessor',
                    'OPTIONS': {
                        'whitelist': []
                    }
                },
            ]
        }
    }
}
EVENT_TRACKING_PROCESSORS = []

#################################### CELERY ####################################

app = Celery('enterprise')  # pylint: disable=invalid-name
app.config_from_object('django.conf:settings')

CELERY_ALWAYS_EAGER = True

CLEAR_REQUEST_CACHE_ON_TASK_COMPLETION = False

JWT_AUTH = {
    'JWT_AUDIENCE': 'test-aud',
    'JWT_DECODE_HANDLER': 'edx_rest_framework_extensions.auth.jwt.decoder.jwt_decode_handler',
    'JWT_ISSUER': 'test-iss',
    'JWT_LEEWAY': 1,
    'JWT_SECRET_KEY': 'test-key',
    'JWT_SUPPORTED_VERSION': '1.0.0',
    'JWT_VERIFY_AUDIENCE': False,
    'JWT_VERIFY_EXPIRATION': True,

    # JWT_ISSUERS enables token decoding for multiple issuers (Note: This is not a native DRF-JWT field)
    # We use it to allow different values for the 'ISSUER' field, but keep the same SECRET_KEY and
    # AUDIENCE values across all issuers.
    'JWT_ISSUERS': [
        {
            'ISSUER': 'test-issuer-1',
            'SECRET_KEY': 'test-secret-key',
            'AUDIENCE': 'test-audience',
        },
        {
            'ISSUER': 'test-issuer-2',
            'SECRET_KEY': 'test-secret-key',
            'AUDIENCE': 'test-audience',
        }
    ],
}
