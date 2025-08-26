from rest_framework import status

from apps.settings.models import FeatureActivation
from apps.settings.services import feature_url


class FeatureMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return self.process_response(request, response)

    def process_response(self, request, response):
        try:
            response.render()
        except Exception:
            pass

        blocked_features = list(FeatureActivation.objects.filter(active=False).values_list("feature", flat=True))
        blocked_urls = [feature_url()[feature_name] for feature_name in blocked_features]
        for blocked_url in blocked_urls:
            if blocked_url in request.path:
                error_message = "این قابلیت از سامانه غیرفعال شده است"
                response.content = f'{{"error": "{error_message}"}}'.encode("utf-8")
                response.status_code = status.HTTP_423_LOCKED

        return response
