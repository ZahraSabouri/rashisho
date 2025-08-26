from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.community import reports
from apps.community.api.views import community

app_name = "community"

router = DefaultRouter()
router.register("", community.CommunityViewSet, basename="community")

urlpatterns = [
    path("community-members-report/", reports.CommunityMembersReportAPV.as_view(), name="community-members-report"),
    path("", include(router.urls)),
]
