from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_nested.routers import NestedDefaultRouter

from apps.exam import reports
from apps.exam.api.views import answer, belbin, exam, exam_result, neo

app_name = "exam"



router = DefaultRouter()
router.register("belbin-question", belbin.BelbinQuestionVS, "belbin-question")
router.register("belbin-user-answers", belbin.BelbinUserAnswer, basename="belbin-user-answer")
router.register("belbin-multi-question", belbin.BelbinMultiCreate, "belbin-multi-question")
router.register("neo-question", neo.NeoQuestionViewSet, "neo-question")
router.register("general-exam", exam.GeneralExamVS, "general-exam")
router.register("user-answer", answer.UserAnswerViewSet, "user-answer")

neo_router = NestedDefaultRouter(router, "neo-question", lookup="neo")
neo_router.register("neo-option", neo.NeoOptionViewSet, basename="neo-option")
neo_router.register("user-answer", neo.NeoUserAnswerViewSet, basename="user-answer")

general_router = NestedDefaultRouter(router, "general-exam", lookup="exam")
general_router.register("answer", exam.GeneralQuestionAnswerVS, "general-answer")

urlpatterns = [
    path("belbin-report/", reports.BelbinReportAPV.as_view(), name="belbin-report"),
    path("neo-report/", reports.NeoReportAPV.as_view(), name="neo-report"),
    path("general-report/", reports.GeneralReportAPV.as_view(), name="general-report"),
    path("neo-users-count/", neo.NeoFinishedUsersCount.as_view(), name="neo-users-count"),
    path("belbin-users-count/", belbin.BelbinFinishedUsersCount.as_view(), name="belbin-users-count"),
    path("general-users-info/<uuid:pk>", exam.GeneralExamUsersInfo.as_view(), name="general-users-info"),
    path("general-select/", exam.GeneralExamSelectAPV.as_view(), name="general-select"),
    path("results/", exam_result.ExamResultAPV.as_view(), name="results"),
    path("remove-answer/", belbin.RemoveUserExamAnswer.as_view(), name="remove-answer"),
    path("", include(router.urls)),
    path("", include(general_router.urls)),
    path("", include(neo_router.urls)),
]
