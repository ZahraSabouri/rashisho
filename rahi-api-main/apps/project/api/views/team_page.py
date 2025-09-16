from rest_framework import status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.exceptions import ValidationError, PermissionDenied
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone

from apps.project.models import Team, TeamChatMessage, TeamOnlineMeeting, TeamUnstableTask
from apps.project.api.serializers.team_page import (
    TeamPageSerializer, TeamChatMessageSerializer, CreateChatMessageSerializer,
    TeamOnlineMeetingSerializer, TeamUnstableTaskSerializer
)
from apps.api.permissions import IsUser, IsSysgod


class TeamPageView(APIView):
    permission_classes = [IsUser | IsSysgod]
    
    def get(self, request, team_id):
        team = get_object_or_404(Team, id=team_id)
        
        # Check if user can view this team
        if not self._can_user_view_team(request.user, team):
            raise PermissionDenied("شما اجازه مشاهده این تیم را ندارید!")
        
        serializer = TeamPageSerializer(team, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def _can_user_view_team(self, user, team):
        # Team members can always view
        is_member = team.requests.filter(
            user=user, status='A', request_type='JOIN'
        ).exists()
        
        # Admins can view all teams
        is_admin = user.is_staff or user.is_superuser
        
        # For now, allow all authenticated users to view teams
        # You can restrict this based on your business logic
        return is_member or is_admin or True


class TeamChatViewSet(ModelViewSet):
    serializer_class = TeamChatMessageSerializer
    permission_classes = [IsUser | IsSysgod]
    
    def get_queryset(self):
        team_id = self.kwargs.get('team_id')
        if not team_id:
            return TeamChatMessage.objects.none()
        
        team = get_object_or_404(Team, id=team_id)
        
        # Verify user can access this team's chat
        if not self._can_user_access_chat(self.request.user, team):
            return TeamChatMessage.objects.none()
        
        return team.chat_messages.select_related('user').order_by('-created_at')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CreateChatMessageSerializer
        return TeamChatMessageSerializer
    
    def create(self, request, team_id=None):
        team = get_object_or_404(Team, id=team_id)
        
        # Verify user is team member
        if not self._can_user_access_chat(request.user, team):
            raise PermissionDenied("شما اجازه ارسال پیام در این تیم را ندارید!")
        
        serializer = CreateChatMessageSerializer(
            data=request.data,
            context={'request': request, 'team': team}
        )
        serializer.is_valid(raise_exception=True)
        message = serializer.save()
        
        # Return the created message with full details
        response_serializer = TeamChatMessageSerializer(
            message, context={'request': request}
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    def update(self, request, team_id=None, pk=None):
        team = get_object_or_404(Team, id=team_id)
        message = get_object_or_404(TeamChatMessage, id=pk, team=team)
        
        # Only message author can edit
        if message.user != request.user:
            raise PermissionDenied("شما فقط می‌توانید پیام‌های خود را ویرایش کنید!")
        
        # Update message
        message.message = request.data.get('message', message.message)
        message.is_edited = True
        message.edited_at = timezone.now()
        message.save()
        
        serializer = TeamChatMessageSerializer(message, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def destroy(self, request, team_id=None, pk=None):
        team = get_object_or_404(Team, id=team_id)
        message = get_object_or_404(TeamChatMessage, id=pk, team=team)
        
        # Check permissions: message author or team leader
        is_author = message.user == request.user
        is_leader = team.requests.filter(
            user=request.user, status='A', user_role='C', request_type='JOIN'
        ).exists()
        
        if not (is_author or is_leader):
            raise PermissionDenied("شما اجازه حذف این پیام را ندارید!")
        
        message.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    def _can_user_access_chat(self, user, team):
        return team.requests.filter(
            user=user, status='A', request_type='JOIN'
        ).exists()
    
    @action(methods=['GET'], detail=False, url_path='history')
    def get_chat_history(self, request, team_id=None):
        team = get_object_or_404(Team, id=team_id)
        
        if not self._can_user_access_chat(request.user, team):
            raise PermissionDenied("شما اجازه مشاهده تاریخچه چت را ندارید!")
        
        # Get pagination params
        page_size = int(request.query_params.get('page_size', 20))
        page = int(request.query_params.get('page', 1))
        offset = (page - 1) * page_size
        
        messages = team.chat_messages.select_related('user')[offset:offset + page_size]
        total_count = team.chat_messages.count()
        
        serializer = TeamChatMessageSerializer(
            messages, many=True, context={'request': request}
        )
        
        return Response({
            'messages': serializer.data,
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'has_more': offset + page_size < total_count
        }, status=status.HTTP_200_OK)


class TeamMeetingViewSet(ModelViewSet):
    serializer_class = TeamOnlineMeetingSerializer
    permission_classes = [IsUser | IsSysgod]
    
    def get_queryset(self):
        team_id = self.kwargs.get('team_id')
        if not team_id:
            return TeamOnlineMeeting.objects.none()
        
        team = get_object_or_404(Team, id=team_id)
        return team.online_meetings.order_by('-created_at')
    
    def create(self, request, team_id=None):
        if not (request.user.is_staff or request.user.is_superuser):
            raise PermissionDenied("فقط ادمین می‌تواند جلسه آنلاین ایجاد کند!")
        
        team = get_object_or_404(Team, id=team_id)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        meeting = serializer.save(team=team, created_by=request.user)
        return Response(
            TeamOnlineMeetingSerializer(meeting, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )
    
    def update(self, request, team_id=None, pk=None):
        if not (request.user.is_staff or request.user.is_superuser):
            raise PermissionDenied("فقط ادمین می‌تواند جلسه را ویرایش کند!")
        
        return super().update(request, pk)
    
    def destroy(self, request, team_id=None, pk=None):
        """Delete meeting (admin only)"""
        if not (request.user.is_staff or request.user.is_superuser):
            raise PermissionDenied("فقط ادمین می‌تواند جلسه را حذف کند!")
        
        return super().destroy(request, pk)


class TeamTaskViewSet(ModelViewSet):
    serializer_class = TeamUnstableTaskSerializer
    permission_classes = [IsUser | IsSysgod]
    
    def get_queryset(self):
        team_id = self.kwargs.get('team_id')
        if not team_id:
            return TeamUnstableTask.objects.none()
        
        team = get_object_or_404(Team, id=team_id)
        return team.unstable_tasks.select_related('assigned_to').order_by('-created_at')
    
    def create(self, request, team_id=None):
        team = get_object_or_404(Team, id=team_id)
        
        # Check if user can manage team
        can_manage = team.requests.filter(
            user=request.user, status='A', user_role__in=['C', 'D'], request_type='JOIN'
        ).exists()
        
        if not can_manage:
            raise PermissionDenied("فقط سرگروه و قائم مقام می‌توانند کار ایجاد کنند!")
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        task = serializer.save(team=team)
        return Response(
            TeamUnstableTaskSerializer(task, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(methods=['POST'], detail=True, url_path='mark-complete')
    def mark_complete(self, request, team_id=None, pk=None):
        team = get_object_or_404(Team, id=team_id)
        task = get_object_or_404(TeamUnstableTask, id=pk, team=team)
        
        # Check if user can complete this task
        can_complete = (
            task.assigned_to == request.user or  # Assigned user
            team.requests.filter(  # Team leaders/deputies
                user=request.user, status='A', user_role__in=['C', 'D'], request_type='JOIN'
            ).exists()
        )
        
        if not can_complete:
            raise PermissionDenied("شما اجازه تکمیل این کار را ندارید!")
        
        from django.utils import timezone
        task.is_completed = True
        task.completed_at = timezone.now()
        task.save()
        
        serializer = TeamUnstableTaskSerializer(task, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    