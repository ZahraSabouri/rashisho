from django.urls import path

from apps.account import reports
from apps.account.api.views import user

app_name = "account"

urlpatterns = [
    path("me/", user.MeAV.as_view(), name="me"),
    path("users/", user.UserAV.as_view(), name="users"),
    path("info-update/", user.UpdateInfo.as_view(), name="info-update"),
    path("accept-terms/", user.AcceptTerms.as_view(), name="accept-terms"),
    path("users-report/", reports.UsersReportAPV.as_view(), name="users-report"),
]
