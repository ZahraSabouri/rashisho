from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.comments.api.views import CommentViewSet, CommentModerationViewSet

app_name = 'comments'

router = DefaultRouter()
router.register(r'comments', CommentViewSet, basename='comment')
router.register(r'moderation-logs', CommentModerationViewSet, basename='moderation-log')

urlpatterns = [
    path('', include(router.urls)),
]

# URL patterns generated:
# GET /api/comments/comments/ - List comments
# POST /api/comments/comments/ - Create comment  
# GET /api/comments/comments/{id}/ - Get comment detail
# PUT/PATCH /api/comments/comments/{id}/ - Update comment
# DELETE /api/comments/comments/{id}/ - Delete comment
# POST /api/comments/comments/{id}/react/ - Add/update reaction
# DELETE /api/comments/comments/{id}/remove_reaction/ - Remove reaction
# POST /api/comments/comments/{id}/approve/ - Approve comment (admin)
# POST /api/comments/comments/{id}/reject/ - Reject comment (admin)
# POST /api/comments/comments/bulk_action/ - Bulk actions (admin)
# GET /api/comments/comments/export/ - Export comments CSV (admin)
# GET /api/comments/comments/statistics/ - Get comment statistics
# GET /api/comments/moderation-logs/ - List moderation logs (admin)
# GET /api/comments/moderation-logs/{id}/ - Get moderation log detail (admin)