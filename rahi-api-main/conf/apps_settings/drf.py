REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.api.pagination.Pagination",
    "PAGE_SIZE": 10,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": ("apps.api.authentication.GetUserProfileAuthentication",),
}

# drf-spectacular settings
SPECTACULAR_SETTINGS = {
    'TITLE': 'Rahisho API',
    # 'DESCRIPTION': 'راهی شو - پلتفرم ملی مسابقات مبتنی بر مسئله',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    
    # Register custom authentication extension
    'EXTENSIONS': [
        'apps.api.schema.GetUserProfileAuthenticationExtension',
    ],
    
    # Authentication schemes
    'AUTHENTICATION_WHITELIST': [
        'apps.api.authentication.GetUserProfileAuthentication',
    ],
    
    # Schema customization
    'SCHEMA_PATH_PREFIX': '/api/v1/',
    'COMPONENT_SPLIT_REQUEST': True,
    'SORT_OPERATIONS': False,
}