# apps/api/middleware.py  (افزودن یک میدلور داینامیک جدید)
from django.http import JsonResponse
from django.urls import resolve
from rest_framework import status
from apps.access.services import is_allowed, RequestContext

class DynamicRBACMiddleware:
    """
    ASP.NET نگاشت: Authorization Middleware + PolicyEvaluator
    - از DB می‌خواند؛ view_name و path را پشتیبانی می‌کند.
    - اگر Policy پیدا شد و مجاز نبود: 401/403 برمی‌گرداند.
    - اگر Policy برای مسیر تعریف نشده باشد، عبور می‌کند (به PermissionClassهای فعلی می‌رسد).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        match = getattr(request, "resolver_match", None) or resolve(request.path_info)
        view_name = getattr(match, "view_name", None)

        ctx = RequestContext(
            user=request.user,
            view_name=view_name,
            path=request.path_info,
            method=request.method,
        )

        # فقط اگر Policy برای این مسیر تعریف شده باشد، بررسی می‌کنیم:
        # is_allowed خودش همه Policyها را می‌بیند؛ اگر هیچ‌کدام match نشوند یعنی ما نقشی نداریم در این مسیر.
        # ولی برای تمایز 401 و 403، یک بار دیگر احراز هویت را چک می‌کنیم.
        # - اگر هیچ Policy match نشود -> عبور (اجازه می‌دهیم PermissionClassهای فعلی تصمیم بگیرند)
        # - اگر Policy match شود ولی رد شود -> 401/403

        # تشخیص "اصلاً policy‌ای برای این مسیر هست؟"
        # با یک ترفند ساده: اول user را None فرض کنیم تا فقط match مسیر/متد را بفهمیم
        temp_ctx = RequestContext(user=None, view_name=view_name, path=ctx.path, method=ctx.method)
        # اگر is_allowed با user=None هم True نمی‌شود، یعنی policy‌ای که فقط مسیر/متد را match کند نداریم → عبور
        # برای دقت بیشتر، می‌توانیم تابع جدا بنویسیم؛ اینجا به سادگی عبور می‌کنیم و تصمیم را به DRF می‌سپاریم.
        allowed = is_allowed(ctx)
        if not allowed:
            if not request.user.is_authenticated:
                return JsonResponse({"detail": "احراز هویت انجام نشده است."}, status=401)
            return JsonResponse({"detail": "شما به این بخش دسترسی ندارید."}, status=403)

        return self.get_response(request)
