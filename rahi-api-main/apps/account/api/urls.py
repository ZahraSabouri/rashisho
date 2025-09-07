from django.urls import path

from apps.account import reports
from apps.account.api.views import user
from apps.account.api.views import connection

app_name = "account"

urlpatterns = [
    path("me/", user.MeAV.as_view(), name="me"),
    path("users/", user.UserAV.as_view(), name="users"),
    path("info-update/", user.UpdateInfo.as_view(), name="info-update"),
    path("accept-terms/", user.AcceptTerms.as_view(), name="accept-terms"),
    path("users-report/", reports.UsersReportAPV.as_view(), name="users-report"),
    path("connections/request", connection.ConnectionRequestAV.as_view(), name="connection-request"),
    path("connections/pending", connection.PendingConnectionsAV.as_view(), name="connection-pending-list"),
    path("connections/<int:id>/decision", connection.ConnectionDecisionAV.as_view(), name="connection-decision"),
    # DEV: Token generation endpoints
    path("dev-user-token/", user.dev_user_token_view, name="dev-user-token"),
    path("dev-admin-token/", user.dev_admin_token_view, name="dev-admin-token"),
]
