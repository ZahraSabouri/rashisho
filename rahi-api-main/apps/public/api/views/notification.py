from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter

from apps.api.permissions import IsAdminOrReadOnlyPermission
from apps.api.schema import TaggedAutoSchema
from apps.api.pagination import Pagination
from apps.public.models import Announcement, UserNotification, AnnouncementReceipt
from apps.public.api.serializers.notification import (
    AnnouncementSerializer,
    AnnouncementOutSerializer,
    UserNotificationSerializer,
    UserNotificationOutSerializer,
    SnoozeSer,
    MarkReadSer,
)

User = get_user_model()

class AnnouncementViewSet(viewsets.ModelViewSet):
    schema = TaggedAutoSchema(tags=["Announcements"])
    serializer_class = AnnouncementSerializer
    queryset = Announcement.objects.all()
    permission_classes = [IsAdminOrReadOnlyPermission]
    ordering_fields = "__all__"
    pagination_class = Pagination

    @extend_schema(
        tags=["Announcements"],
        description="Get the single active اعلان for current user. Returns 204 if acknowledged/snoozed.",
        responses={200: AnnouncementOutSerializer, 204: OpenApiResponse(response=None)},
    )
    @action(methods=["get"], detail=False, url_path="active", permission_classes=[permissions.AllowAny])
    def active(self, request):
        announcement = Announcement.objects.filter(is_active=True).order_by("-created_at").first()
        if not announcement:
            return Response(status=status.HTTP_204_NO_CONTENT)

        if request.user.is_authenticated:
            receipt, _ = AnnouncementReceipt.objects.get_or_create(
                announcement=announcement, user=request.user
            )
            if receipt.is_suppressed_now():
                return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = AnnouncementOutSerializer(announcement, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Announcements"],
        parameters=[
            OpenApiParameter("user_id", str, OpenApiParameter.QUERY, required=False, description="UUID کاربر خاص"),
        ],
        description="Admin: Get all announcement receipts (user interactions) with pagination. Filter by user_id if provided.",
        responses={200: "Paginated announcement receipts"}
    )
    @action(methods=["get"], detail=False, url_path="admin/receipts", permission_classes=[permissions.IsAdminUser])
    def admin_receipts(self, request):
        """Admin: Get all announcement receipts with pagination"""
        user_id = request.query_params.get('user_id')
        
        queryset = AnnouncementReceipt.objects.select_related('announcement', 'user').order_by('-created_at')
        
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        # Apply pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            data = []
            for receipt in page:
                data.append({
                    "id": str(receipt.id),
                    "announcement": {
                        "id": str(receipt.announcement.id),
                        "title": receipt.announcement.title,
                        "created_at": receipt.announcement.created_at
                    },
                    "user": {
                        "id": str(receipt.user.id),
                        "name": f"{receipt.user.user_info.get('first_name', '')} {receipt.user.user_info.get('last_name', '')}",
                        "mobile": receipt.user.user_info.get('mobile_number', ''),
                    },
                    "acknowledged_at": receipt.acknowledged_at,
                    "snoozed_until": receipt.snoozed_until,
                    "created_at": receipt.created_at,
                })
            return self.get_paginated_response(data)
        
        # Fallback if pagination fails
        return Response({"results": [], "count": 0})

    def create(self, request, *args, **kwargs):
        """Admin can create announcements for specific users or all users"""
        if not request.user.is_staff:
            return Response({"detail": "فقط ادمین می‌تواند اعلان ایجاد کند."}, 
                        status=status.HTTP_403_FORBIDDEN)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Create the announcement
        announcement = serializer.save()
        
        # Handle target users (ManyToMany relationship)
        target_users = request.data.get('target_users', [])
        if target_users:
            announcement.target_users.set(target_users)
            message = f"اعلان برای {len(target_users)} کاربر ایجاد شد."
        else:
            # Empty target_users means "for all users"
            message = "اعلان برای همه کاربران ایجاد شد."
        
        return Response(
            {
                "announcement": AnnouncementOutSerializer(announcement, context={'request': request}).data,
                "message": message
            },
            status=status.HTTP_201_CREATED
        )

    @extend_schema(
        tags=["Announcements"],
        parameters=[
            OpenApiParameter("user_id", str, OpenApiParameter.QUERY, required=False, description="UUID کاربر خاص"),
        ],
        description="Admin: Get all announcements with their targeting info. Filter by user_id to see what announcements target that user.",
    )
    @action(methods=["get"], detail=False, url_path="admin/all", permission_classes=[permissions.IsAdminUser])
    def admin_all(self, request):
        """Admin: Get all announcements with targeting details"""
        user_id = request.query_params.get('user_id')
        
        queryset = self.get_queryset().prefetch_related('target_users').order_by('-created_at')
        
        if user_id:
            # Filter to announcements that target this specific user (or all users)
            queryset = queryset.filter(Q(target_users__id=user_id) | Q(target_users__isnull=True))
        
        # Apply pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            data = []
            for announcement in page:
                target_users = announcement.target_users.all()
                data.append({
                    "id": str(announcement.id),
                    "title": announcement.title,
                    "description": announcement.description,
                    "is_active": announcement.is_active,
                    "created_at": announcement.created_at,
                    "target_type": "specific_users" if target_users.exists() else "all_users",
                    "target_count": target_users.count(),
                    "receipts_count": announcement.receipts.count(),
                    "acknowledged_count": announcement.receipts.filter(acknowledged_at__isnull=False).count(),
                })
            return self.get_paginated_response(data)
        
        return Response({"results": [], "count": 0})

    @extend_schema(
        tags=["Announcements"],
        description='Mark اعلان as "Got it" (never show again)',
        responses={200: OpenApiResponse(response=None)},
    )
    @action(methods=["post"], detail=True, url_path="ack", permission_classes=[permissions.IsAuthenticated])
    def ack(self, request, pk=None):
        """Mark اعلان as acknowledged - never show again"""
        announcement = self.get_object()
        receipt, _ = AnnouncementReceipt.objects.get_or_create(
            announcement=announcement, user=request.user
        )
        receipt.acknowledged_at = timezone.now()
        receipt.snoozed_until = None
        receipt.save(update_fields=["acknowledged_at", "snoozed_until"])
        return Response(status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Announcements"],
        request=SnoozeSer,
        description='Snooze اعلان ("Remind later")',
        responses={200: OpenApiResponse(response=None)},
    )
    @action(methods=["post"], detail=True, url_path="snooze", permission_classes=[permissions.IsAuthenticated])
    def snooze(self, request, pk=None):
        """Snooze اعلان - will show again after specified time"""
        announcement = self.get_object()
        serializer = SnoozeSer(data=request.data)
        serializer.is_valid(raise_exception=True)
        minutes = serializer.validated_data["minutes"]
        
        receipt, _ = AnnouncementReceipt.objects.get_or_create(
            announcement=announcement, user=request.user
        )
        receipt.snoozed_until = timezone.now() + timedelta(minutes=minutes)
        receipt.save(update_fields=["snoozed_until"])
        return Response(status=status.HTTP_200_OK)


class NotificationViewSet(viewsets.ModelViewSet):
    """
    آگهی (Notifications) - ViewSet for managing user notifications.
    Supports read/unread, paginated lists, admin creation for specific/all users.
    """
    schema = TaggedAutoSchema(tags=["Notifications"])
    serializer_class = UserNotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = Pagination

    def get_queryset(self):
        """Regular users see only their notifications"""
        if getattr(self, 'action', None) in ['admin_all', 'admin_user_notifications']:
            # Admin actions use different querysets
            return UserNotification.objects.all()
        return UserNotification.objects.filter(user=self.request.user).order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'create':
            return UserNotificationSerializer
        return UserNotificationOutSerializer

    def get_permissions(self):
        """Admin creation, user consumption"""
        if self.action == 'create':
            return [permissions.IsAdminUser()]
        if self.action in ['admin_all', 'admin_user_notifications']:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    @extend_schema(
        tags=["Notifications"],
        parameters=[
            OpenApiParameter("user_id", str, OpenApiParameter.QUERY, required=False, description="UUID کاربر خاص"),
        ],
        description="Admin: Get all notifications with pagination. Filter by user_id if provided.",
    )
    @action(methods=["get"], detail=False, url_path="admin/all", permission_classes=[permissions.IsAdminUser])
    def admin_all(self, request):
        """Admin: Get all notifications with pagination"""
        user_id = request.query_params.get('user_id')
        
        queryset = UserNotification.objects.select_related('user').order_by('-created_at')
        
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        # Apply pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            data = []
            for notification in page:
                data.append({
                    "id": str(notification.id),
                    "title": notification.title,
                    "body": notification.body,
                    "kind": notification.kind,
                    "url": notification.url,
                    "is_read": notification.is_read,
                    "read_at": notification.read_at,
                    "created_at": notification.created_at,
                    "user": {
                        "id": str(notification.user.id),
                        "name": f"{notification.user.user_info.get('first_name', '')} {notification.user.user_info.get('last_name', '')}",
                        "mobile": notification.user.user_info.get('mobile_number', ''),
                    }
                })
            return self.get_paginated_response(data)
        
        return Response({"results": [], "count": 0})

    @extend_schema(
        tags=["Notifications"],
        parameters=[
            OpenApiParameter("user_id", str, OpenApiParameter.QUERY, required=True, description="UUID کاربر مورد نظر"),
        ],
        description="Admin: Get all notifications for a specific user with pagination.",
    )
    @action(methods=["get"], detail=False, url_path="admin/user", permission_classes=[permissions.IsAdminUser])
    def admin_user_notifications(self, request):
        """Admin: Get all notifications for specific user"""
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response({"detail": "پارامتر user_id الزامی است."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"detail": "کاربر پیدا نشد."}, status=status.HTTP_404_NOT_FOUND)
        
        queryset = UserNotification.objects.filter(user=user).order_by('-created_at')
        
        # Apply pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = UserNotificationOutSerializer(page, many=True, context={'request': request})
            response_data = self.get_paginated_response(serializer.data).data
            response_data['user_info'] = {
                "id": str(user.id),
                "name": f"{user.user_info.get('first_name', '')} {user.user_info.get('last_name', '')}",
                "mobile": user.user_info.get('mobile_number', ''),
            }
            return Response(response_data)
        
        return Response({"results": [], "count": 0})

    def create(self, request, *args, **kwargs):
        """Admin can create notifications for specific users or all users"""
        if not request.user.is_staff:
            return Response({"detail": "فقط ادمین می‌تواند آگهی ایجاد کند."}, 
                        status=status.HTTP_403_FORBIDDEN)
        
        serializer = UserNotificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Get target users
        target_users = request.data.get('target_users', [])
        
        if target_users:
            # Create notifications for specific users
            users = User.objects.filter(id__in=target_users)
            created_count = 0
            for user in users:
                UserNotification.objects.create(
                    user=user,
                    title=serializer.validated_data['title'],
                    body=serializer.validated_data['body'],
                    kind=serializer.validated_data.get('kind', 'info'),
                    payload=serializer.validated_data.get('payload', {}),
                    url=serializer.validated_data.get('url', ''),
                )
                created_count += 1
            message = f"آگهی برای {created_count} کاربر ایجاد شد."
        else:
            # Create notifications for ALL users
            all_users = User.objects.all()
            created_count = 0
            for user in all_users:
                UserNotification.objects.create(
                    user=user,
                    title=serializer.validated_data['title'],
                    body=serializer.validated_data['body'],
                    kind=serializer.validated_data.get('kind', 'info'),
                    payload=serializer.validated_data.get('payload', {}),
                    url=serializer.validated_data.get('url', ''),
                )
                created_count += 1
            message = f"آگهی برای همه کاربران ({created_count} نفر) ایجاد شد."
        
        return Response(
            {
                "message": message,
                "created_count": created_count,
                "notification_sample": {
                    "title": serializer.validated_data['title'],
                    "body": serializer.validated_data['body'],
                    "kind": serializer.validated_data.get('kind', 'info'),
                }
            },
            status=status.HTTP_201_CREATED
        )

    @extend_schema(
        tags=["Notifications"],
        description="Get unread notifications count for current user",
        responses={200: {"type": "object", "properties": {"unread_count": {"type": "integer"}}}},
    )
    @action(methods=["get"], detail=False, url_path="unread-count", permission_classes=[permissions.IsAuthenticated])
    def unread_count(self, request):
        """Get unread notifications count"""
        count = self.get_queryset().filter(is_read=False).count()
        return Response({"unread_count": count}, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Notifications"],
        request=MarkReadSer,
        description="Mark multiple notifications as read",
        responses={200: OpenApiResponse(response=None)},
    )
    @action(methods=["post"], detail=False, url_path="mark-read", permission_classes=[permissions.IsAuthenticated])
    def mark_read(self, request):
        """Mark notifications as read (batch operation)"""
        serializer = MarkReadSer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data["ids"]
        
        updated_count = (
            self.get_queryset()
            .filter(id__in=ids, is_read=False)
            .update(is_read=True, read_at=timezone.now())
        )
        
        return Response(
            {"message": f"{updated_count} آگهی به عنوان خوانده شده علامت‌گذاری شد."},
            status=status.HTTP_200_OK
        )
    
    @extend_schema(
        tags=["Notifications"],
        parameters=[
            OpenApiParameter(name="unread", type=bool, required=False, description="فقط خوانده‌نشده‌ها"),
            OpenApiParameter(name="page", type=int, required=False),
            OpenApiParameter(name="page_size", type=int, required=False),
        ],
        responses={200: UserNotificationOutSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        if request.user.is_staff and not request.query_params.get('user_id'):
            # Admin sees all notifications
            queryset = self.get_queryset().order_by("-created_at")
        else:
            # Regular user sees only their notifications
            queryset = UserNotification.objects.filter(user=request.user).order_by("-created_at")
        
        unread = str(request.query_params.get("unread", "")).lower() in ("1", "true", "t", "yes")
        if unread:
            queryset = queryset.filter(is_read=False)
        
        paginator = Pagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = UserNotificationOutSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)


        """Mark multiple notifications as read"""
        serializer = MarkReadSer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data["ids"]
        
        updated = UserNotification.objects.filter(
            user=request.user, id__in=ids, is_read=False
        ).update(is_read=True, read_at=timezone.now())
        
        return Response({"updated": updated}, status=status.HTTP_200_OK)


        """Get count of unread notifications"""
        count = UserNotification.objects.filter(user=request.user, is_read=False).count()
        return Response({"unread": count}, status=status.HTTP_200_OK)