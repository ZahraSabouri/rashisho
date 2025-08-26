from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import city, connection, feature_activation, language, province, skill, study_field, university

app_name = "settings"

router = DefaultRouter()

router.register("province", province.ProvinceViewSet, basename="province")
router.register("city", city.CityViewSet, basename="city")
router.register("study-field", study_field.StudyFieldViewSet, basename="study-field")
router.register("university", university.UniversityViewSet, basename="university")
router.register("language", language.ForeignLanguageViewSet, basename="language")
router.register("skill", skill.SkillViewSet, basename="skill")
router.register("connection", connection.ConnectionWayViewSet, basename="connection")
router.register("feature-activation", feature_activation.FeatureActivationVS, basename="feature-activation")

urlpatterns = [
    path("", include(router.urls)),
]
