from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.public.api.views import (
    about_us,
    common_questions,
    competition_rule,
    contact_information,
    contact_us,
    footer,
    notification,
    ticket,
    user_profile_process,
)

app_name = "public"

router = DefaultRouter()

router.register("notification", notification.NotificationViewSet, basename="notification")
router.register("user-notifications", notification.UserNotificationViewSet, "user-notifications")
router.register("common-questions", common_questions.CommonQuestionsViewSet, basename="common-questions")
router.register("competition-rule", competition_rule.CompetitionRuleViewSet, basename="competition-rule")
router.register("contact-info", contact_information.ContactInformationViewSet, basename="contact-info")
router.register("contact-us", contact_us.ContactUsViewSet, basename="contact-us")
router.register("about-us", about_us.AboutUsViewSet, basename="about-us")
router.register("footer", footer.FooterViewSet, basename="footer")
router.register("ticket", ticket.CommentViewSet, basename="ticket")
router.register("department", ticket.DepartmentViewSet, basename="department")

urlpatterns = [
    path("user-profile-process/", user_profile_process.UserProfileProcess.as_view(), name="user-profile-process"),
    path("", include(router.urls)),
]
