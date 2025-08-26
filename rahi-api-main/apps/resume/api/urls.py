from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_nested.routers import NestedSimpleRouter

from apps.resume import reports
from apps.resume.api.views import certificate, connection, education, language, project, resume, skill, work_experience

app_name = "resume"

router = DefaultRouter()

router.register("", resume.ResumeViewSet, basename="resume")

resume_router = NestedSimpleRouter(router, "", lookup="resume")
resume_router.register("education", education.ResumeEducationViewSet, basename="education")
resume_router.register("work-experience", work_experience.ResumeWorkExperience, basename="work-experience")
resume_router.register("skill", skill.ResumeSkillViewSet, basename="skill")
resume_router.register("language", language.ResumeLanguageViewSet, basename="language")
resume_router.register("certificate", certificate.ResumeCertificateViewSet, basename="certificate")
resume_router.register("connection", connection.ResumeConnectionViewSet, basename="connection")
resume_router.register("resume-project", project.ResumeProjectViewSet, basename="resume-project")

urlpatterns = [
    path("start-resume/", resume.StartResume.as_view(), name="start-resume"),
    path("second-to-third/", resume.ResumeSecondToThirdStep.as_view(), name="second-to-third"),
    path("my-resume/", resume.MyResume.as_view(), name="my-resume"),
    path("resume-report/", reports.ResumeReportAPV.as_view(), name="resume-report"),
    path("", include(router.urls)),
    path("", include(resume_router.urls)),
]
