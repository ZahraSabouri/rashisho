"""
Comments app configuration with signal registration.
"""
from django.apps import AppConfig


class CommentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.comments"
    verbose_name = "نظرات"
    
    def ready(self):
        """Initialize app when Django starts"""
        # Import signals to register them
        import apps.comments.signals