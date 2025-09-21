from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.project.api.views import project, team
from apps.project.api.views.team import TeamRequestViewSet, TeamEnhancedViewSet
from apps.project.api.views.team_invitations import TeamInvitationViewSet, FreeParticipantsViewSet
from apps.project.api.views.team_discovery import TeamDiscoveryViewSet, TeamPageView
from apps.project.api.views.team_announcements import TeamBuildingAnnouncementsView, TeamBuildingRulesView
from apps.project.api.views.team_deputy_management import TeamDeputyManagementViewSet
from apps.project.api.views.team_page import (
    TeamPageView, TeamChatViewSet, TeamMeetingViewSet, TeamTaskViewSet
)
from apps.project.api.views.team_admin import (
    EnhancedTeamReportView, TeamBulkImportView, TeamAdminManagementViewSet
)
from apps.project import reports
from apps.project.api.views import project, tag, project_status, attraction #, team
from apps.project.api.views.team_admin import (
    TeamBuildingSettingsViewSet,
    TeamBuildingStageDescriptionViewSet,
    TeamBuildingControlView,
    UnstableTeamExportImportView
)
from apps.project.api.views.team_invitations import EnhancedTeamInvitationViewSet

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
    path("", include(router.urls)),
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

    
        # === TEAM PAGE FUNCTIONALITY ===
        
        # Complete team page view
        # Team chat endpoints
        path('team/<uuid:team_id>/chat/', TeamChatViewSet.as_view({
                'get': 'list',
                'post': 'create'
        }), name='team-chat'),
        
        path('team/<uuid:team_id>/chat/<int:pk>/', TeamChatViewSet.as_view({
                'get': 'retrieve',
                'put': 'update',
                'patch': 'partial_update',
                'delete': 'destroy'
        }), name='team-chat-detail'),
        
        path('team/<uuid:team_id>/chat/history/', TeamChatViewSet.as_view({
                'get': 'get_chat_history'
        }), name='team-chat-history'),
        
        # Team online meetings endpoints (admin managed)
        path('team/<uuid:team_id>/meetings/', TeamMeetingViewSet.as_view({
                'get': 'list',
                'post': 'create'
        }), name='team-meetings'),
        
        path('team/<uuid:team_id>/meetings/<int:pk>/', TeamMeetingViewSet.as_view({
                'get': 'retrieve',
                'put': 'update',
                'patch': 'partial_update',
                'delete': 'destroy'
        }), name='team-meeting-detail'),
        
        # Team unstable tasks endpoints  
        path('team/<uuid:team_id>/tasks/', TeamTaskViewSet.as_view({
                'get': 'list',
                'post': 'create'
        }), name='team-tasks'),
        
        path('team/<uuid:team_id>/tasks/<int:pk>/', TeamTaskViewSet.as_view({
                'get': 'retrieve',
                'put': 'update',
                'patch': 'partial_update',
                'delete': 'destroy'
        }), name='team-task-detail'),
        
        path('team/<uuid:team_id>/tasks/<int:pk>/mark-complete/', TeamTaskViewSet.as_view({
                'post': 'mark_complete'
        }), name='team-task-complete'),


        # === ENHANCED TEAM ADMIN ENDPOINTS (Step 3) ===

        # Enhanced team export with filtering
        path('team-report-enhanced/', EnhancedTeamReportView.as_view(), name='enhanced-team-report'),

        # Excel import functionality  
        path('team-bulk-import/', TeamBulkImportView.as_view(), name='team-bulk-import'),

        # Advanced team management
        path('admin/teams/', TeamAdminManagementViewSet.as_view({
        'get': 'list',
        'post': 'create'
        }), name='admin-teams'),

        path('admin/teams/<uuid:pk>/', TeamAdminManagementViewSet.as_view({
        'get': 'retrieve', 
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
        }), name='admin-team-detail'),

        path('admin/teams/<uuid:pk>/add-member/', TeamAdminManagementViewSet.as_view({
        'post': 'add_member'
        }), name='admin-team-add-member'),

        path('admin/teams/<uuid:pk>/remove-member/', TeamAdminManagementViewSet.as_view({
        'post': 'remove_member' 
        }), name='admin-team-remove-member'),

        path('admin/teams/<uuid:pk>/change-leader/', TeamAdminManagementViewSet.as_view({
        'post': 'change_leader'
        }), name='admin-team-change-leader'),

        path('admin/teams/statistics/', TeamAdminManagementViewSet.as_view({
        'get': 'get_statistics'
        }), name='admin-team-statistics'),

        
        # === TEAM BUILDING ADMIN CONTROL SYSTEM ===
        
        # 12-stage control system
        path('admin/team-building-settings/', TeamBuildingSettingsViewSet.as_view({
                'get': 'list',
                'post': 'create'
        }), name='team-building-settings'),
        
        path('admin/team-building-settings/<int:pk>/', TeamBuildingSettingsViewSet.as_view({
                'get': 'retrieve',
                'put': 'update', 
                'patch': 'partial_update',
                'delete': 'destroy'
        }), name='team-building-settings-detail'),
        
        # Get all 12 controls in organized format
        path('admin/team-building-settings/all-controls/', 
                TeamBuildingSettingsViewSet.as_view({'get': 'get_all_controls'}),
                name='all-team-building-controls'),
        
        # Bulk update multiple controls
        path('admin/team-building-settings/bulk-update/', 
                TeamBuildingSettingsViewSet.as_view({'post': 'bulk_update_controls'}),
                name='bulk-update-controls'),
        
        # Get specific stage status
        path('admin/team-building-settings/stage-status/<int:stage>/', 
                TeamBuildingSettingsViewSet.as_view({'get': 'get_stage_status'}),
                name='stage-status'),
        
        # === STAGE DESCRIPTIONS MANAGEMENT ===
        
        path('admin/stage-descriptions/', TeamBuildingStageDescriptionViewSet.as_view({
                'get': 'list',
                'post': 'create'
        }), name='stage-descriptions'),
        
        path('admin/stage-descriptions/<int:pk>/', TeamBuildingStageDescriptionViewSet.as_view({
                'get': 'retrieve',
                'put': 'update',
                'patch': 'partial_update', 
                'delete': 'destroy'
        }), name='stage-descriptions-detail'),
        
        # Get all descriptions in organized format
        path('admin/stage-descriptions/all-descriptions/',
                TeamBuildingStageDescriptionViewSet.as_view({'get': 'get_all_descriptions'}),
                name='all-stage-descriptions'),
        
        # === USER-FACING CONTROL API ===
        
        # Simple API for frontend to check what's enabled
        path('team-building-controls/', TeamBuildingControlView.as_view(), name='team-building-controls'),
        
        # === ENHANCED TEAM INVITATIONS ===
        
        # Enhanced invitation with repeat teammate validation
        path('team-building/invite-with-validation/',
                EnhancedTeamInvitationViewSet.as_view({'post': 'invite_user_with_validation'}),
                name='invite-with-validation'),
        
        # Get available users for invitation
        path('team-building/available-users/',
                EnhancedTeamInvitationViewSet.as_view({'get': 'get_available_users'}),
                name='available-users'),
        
        # Check if invitation is valid before sending
        path('team-building/check-invitation-validity/',
                EnhancedTeamInvitationViewSet.as_view({'post': 'check_invitation_validity'}),
                name='check-invitation-validity'),
        
        # === UNSTABLE TEAM EXPORT/IMPORT ===
        
        # Export unstable teams to Excel
        path("admin/unstable-teams/export/",
                UnstableTeamExportImportView.as_view({"get": "export_unstable_teams"}),
                name="export-unstable-teams",),
        
        # Import teams from Excel
        path("admin/unstable-teams/import/",
                UnstableTeamExportImportView.as_view({"post": "import_unstable_teams"}),
                name="import-unstable-teams"),
        
        # Auto-complete unstable teams
        path("admin/unstable-teams/auto-complete/",
                UnstableTeamExportImportView.as_view({"post": "auto_complete_unstable_teams"}),
                name="auto-complete-unstable-teams"),

        path(
                'team-request/users-status/', 
                TeamRequestViewSet.as_view({'get': 'users_status'}), 
                name='team-request-users-status'
        ),
        path(
                'team-request/send-invitation/', 
                TeamInvitationViewSet.as_view({'post': 'invite_user_to_team'}), 
                name='team-request-send-invitation'
        ),
        path(
                'team-request/respond-invitation/', 
                TeamInvitationViewSet.as_view({'post': 'respond_to_invitation'}), 
                name='team-request-respond-invitation'
        ),
        path(
                'team-request/propose-team/', 
                TeamInvitationViewSet.as_view({'post': 'propose_team_formation'}), 
                name='team-request-propose-team'
        ),

        ])),
    ]