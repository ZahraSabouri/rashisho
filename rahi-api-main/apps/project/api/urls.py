from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.project.api.views import project, team
from apps.project.api.views.team import TeamRequestViewSet, TeamEnhancedViewSet
from apps.project.api.views.team_invitations import TeamInvitationViewSet, FreeParticipantsViewSet
from apps.project.api.views.team_discovery import TeamDiscoveryViewSet, TeamPageView
from apps.project.api.views.team_announcements import TeamBuildingAnnouncementsView, TeamBuildingRulesView
from apps.project.api.views.team_deputy_management import TeamDeputyManagementViewSet

from apps.project import reports
from apps.project.api.views import project, tag, project_status, attraction #, team

app_name = "project"

router = DefaultRouter()

router.register("detail", project.ProjectViewSet, "detail")
router.register("project-priority", project.ProjectPriorityViewSet, "project-priority")
router.register("final-rep", project.FinalRepresentationViewSet, "final-rep")
router.register("scenario", project.ScenarioVS, "scenario")
router.register("task", project.TaskVS, "task")
router.register("derivatives", project.ProjectDerivativesVS, "derivatives")
# router.register("project-members", team.ProjectParticipantsViewSet, "project-members")
# router.register("team-build", team.TeamBuildViewSet, "team-build")
# router.register("team-request", team.TeamRequestViewSet, "team-request")
router.register("final-rep-info", project.FinalRepInfoV2, "final-rep-info")
router.register("home-projects", project.HomePageProjectViewSet, "home-projects")
# router.register("admin-team-create", team.AdminTeamCreationVS, "admin-team-create")
router.register("proposal-info", project.ProposalInfoVS, "proposal-info")
router.register("tag-categories", tag.TagCategoryViewSet, "tag-categories")
router.register("tags", tag.TagViewSet, "tags")
router.register("status", project_status.ProjectStatusViewSet, basename="project-status")
router.register("comments", project.ProjectCommentViewSet, basename="project-comments")
router.register(r'teams', TeamEnhancedViewSet, basename='teams')
router.register(r'team-requests', TeamRequestViewSet, basename='team-requests')
router.register(r'team-invitations', TeamInvitationViewSet, basename='team-invitations')
router.register(r'free-participants', FreeParticipantsViewSet, basename='free-participants')
router.register(r'team-discovery', TeamDiscoveryViewSet, basename='team-discovery')


urlpatterns = [
    # path("my-team/", team.MyTeamAPV.as_view(), name="my-team"),
    # path("team-info/", team.TeamInfoAPV.as_view(), name="team-info"),
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
    # path("user-in-same-project/<uuid:id>/", team.UserInSameProjectAV.as_view(), name="user-in-same-project"),
    # path("project/<uuid:project_id>/tags/", tag.ProjectTagManagementView.as_view(), name="project-tags"),
    path("<uuid:project_id>/tags/", tag.ProjectTagManagementView.as_view(), name="project_tags_alias"),
    path("project/<uuid:project_id>/related/", tag.RelatedProjectsView.as_view(), name="related-projects"),
    path("activation/", project_status.ProjectActivationView.as_view(), name="project-activation"),
    path("status/<uuid:project_id>/", project_status.SingleProjectStatusView.as_view(), name="single-project-status"),
    path("attractions/", attraction.MyAttractionsAV.as_view(), name="my-attractions"),
    path("attractions/reorder/", attraction.MyAttractionsReorderAV.as_view(), name="my-attractions-reorder"),
    path("attractions/<uuid:project_id>/", attraction.MyAttractionDeleteAV.as_view(), name="my-attractions-delete"),

    path('team-building/', include([
            
            # === STEP 1: Team Request Management ===
            
            # Leave team requests
            path('requests/leave/', TeamRequestViewSet.as_view({'post': 'request_leave_team'}), name='request-leave'),
            path('requests/cancel-leave/', TeamRequestViewSet.as_view({'post': 'cancel_leave_request'}), name='cancel-leave'),
            path('requests/approve-leave/', TeamRequestViewSet.as_view({'post': 'approve_leave_request'}), name='approve-leave'),
            
            # Team dissolution
            path('dissolve/', TeamRequestViewSet.as_view({'post': 'request_team_dissolution'}), name='dissolve-team'),
            path('cancel-dissolution/', TeamRequestViewSet.as_view({'post': 'cancel_team_dissolution'}), name='cancel-dissolution'),
            
            # Request management
            path('my-requests/', TeamRequestViewSet.as_view({'get': 'get_my_requests'}), name='my-requests'),
            path('my-team/', TeamEnhancedViewSet.as_view({'get': 'get_my_team'}), name='my-team'),
            
            # === STEP 2: Invitations & Discovery ===
            
            # Team invitations
            path('invite-user/', TeamInvitationViewSet.as_view({'post': 'invite_user_to_team'}), name='invite-user'),
            path('propose-team/', TeamInvitationViewSet.as_view({'post': 'propose_team_formation'}), name='propose-team'),
            path('respond-invitation/', TeamInvitationViewSet.as_view({'post': 'respond_to_invitation'}), name='respond-invitation'),
            path('my-invitations/', TeamInvitationViewSet.as_view({'get': 'get_my_invitations'}), name='my-invitations'),
            
            # Free participants discovery
            path('free-participants/', FreeParticipantsViewSet.as_view({'get': 'list'}), name='free-participants-list'),
            path('free-participants/filters/', FreeParticipantsViewSet.as_view({'get': 'get_available_filters'}), name='free-participants-filters'),
            path('free-participants/actions/', FreeParticipantsViewSet.as_view({'get': 'get_user_actions'}), name='free-participants-actions'),
            
            # Team discovery
            path('discovery/', TeamDiscoveryViewSet.as_view({'get': 'list'}), name='team-discovery'),
            path('discovery/formed/', TeamDiscoveryViewSet.as_view({'get': 'get_formed_teams'}), name='formed-teams'),
            path('discovery/forming/', TeamDiscoveryViewSet.as_view({'get': 'get_forming_teams'}), name='forming-teams'),
            path('discovery/filters/', TeamDiscoveryViewSet.as_view({'get': 'get_available_filters'}), name='discovery-filters'),
            path('discovery/by-province/', TeamDiscoveryViewSet.as_view({'get': 'get_teams_by_province'}), name='teams-by-province'),
            
            # Team page
            path('team/<uuid:team_id>/', TeamPageView.as_view(), name='team-page'),
            path('team/<uuid:team_id>/join-options/', TeamDiscoveryViewSet.as_view({'get': 'get_team_join_options'}), name='team-join-options'),
            
            # === STEP 3: Announcements and Rules ===
            
            # Team building announcements
            path('announcements/', TeamBuildingAnnouncementsView.as_view(), name='team-announcements'),
            path('rules/', TeamBuildingRulesView.as_view(), name='team-rules'),


            # === NEW: DEPUTY MANAGEMENT ENDPOINTS ===
            path('deputy/promote/', TeamRequestViewSet.as_view({'post': 'promote_member_to_deputy'}), name='promote-deputy'),
            path('deputy/demote/', TeamRequestViewSet.as_view({'post': 'demote_deputy_to_member'}), name='demote-deputy'),
            path('leadership-info/', TeamRequestViewSet.as_view({'get': 'get_leadership_info'}), name='leadership-info'),
            
            # Team dissolution
            path('dissolve/', TeamRequestViewSet.as_view({'post': 'request_team_dissolution'}), name='dissolve-team'),
            path('cancel-dissolution/', TeamRequestViewSet.as_view({'post': 'cancel_team_dissolution'}), name='cancel-dissolution'),
            
            ])),
    ]