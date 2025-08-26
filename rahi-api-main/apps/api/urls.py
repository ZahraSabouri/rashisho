from django.urls import include, path

urlpatterns = [
    path("account/", include("apps.account.api.urls")),
    path("resume/", include("apps.resume.api.urls")),
    path("settings/", include("apps.settings.api.urls")),
    path("exam/", include("apps.exam.api.urls")),
    path("public/", include("apps.public.api.urls")),
    path("project/", include("apps.project.api.urls")),
    path("community/", include("apps.community.api.urls")),
]
