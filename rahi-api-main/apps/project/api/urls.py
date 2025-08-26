from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.project import reports
from apps.project.api.views import project, team

app_name = "project"

router = DefaultRouter()

router.register("detail", project.ProjectViewSet, "detail")
router.register("project-priority", project.ProjectPriorityViewSet, "project-priority")
router.register("final-rep", project.FinalRepresentationViewSet, "final-rep")
router.register("scenario", project.ScenarioVS, "scenario")
router.register("task", project.TaskVS, "task")
router.register("derivatives", project.ProjectDerivativesVS, "derivatives")
router.register("project-members", team.ProjectParticipantsViewSet, "project-members")
router.register("team-build", team.TeamBuildViewSet, "team-build")
router.register("team-request", team.TeamRequestViewSet, "team-request")
router.register("final-rep-info", project.FinalRepInfoV2, "final-rep-info")
router.register("home-projects", project.HomePageProjectViewSet, "home-projects")
router.register("admin-team-create", team.AdminTeamCreationVS, "admin-team-create")
router.register("proposal-info", project.ProposalInfoVS, "proposal-info")

urlpatterns = [
    path("my-team/", team.MyTeamAPV.as_view(), name="my-team"),
    path("team-info/", team.TeamInfoAPV.as_view(), name="team-info"),
    path("priority-report/", reports.ProjectPriorityReportAPV.as_view(), name="priority-report"),
    path("team-report/", reports.TeamReportAPV.as_view(), name="team-report"),
    path("final-rep-report/", reports.FinalRepresentationReportAPV.as_view(), name="final-rep-report"),
    path("scenario-report/", reports.ScenarioReportAPV.as_view(), name="scenario-report"),
    path("task-report/", reports.TaskReportAPV.as_view(), name="task-report"),
    path("allocation-report/", reports.AllocatedProjectReportAPV.as_view(), name="allocation-report"),
    path("scenario-task-file/", project.UserScenarioTaskFileAPV.as_view(), name="scenario-task-file"),
    path("user-task-file/", project.UserTaskFileAV.as_view(), name="user-task-file"),
    path("is-team-head/", project.IsTeamHeadAV.as_view(), name="is-team-head"),
    path("task/list", project.ProjectTasksListAV.as_view(), name="tasks-list"),
    path("user-in-same-project/<uuid:id>/", team.UserInSameProjectAV.as_view(), name="user-in-same-project"),
    path("", include(router.urls)),
]
