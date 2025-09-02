import json
from django.urls import reverse
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from rest_framework import status
from rest_framework.test import APITestCase
from model_bakery import baker

from apps.account.models import User
from apps.api.roles import Roles
from apps.comments.models import Comment, CommentReaction, CommentModerationLog
from apps.project.models import Project
from apps.utils.test_tokens import generate_test_token, decode_test_token


class CommentViewSetTest(APITestCase):
    """Test CommentViewSet functionality"""
    
    def setUp(self):
        # Create test users
        self.admin_token = generate_test_token()
        self.admin_user = baker.make(User, user_id=decode_test_token(self.admin_token))
        admin_role = Group.objects.create(name=Roles.sys_god.name)
        self.admin_user.groups.add(admin_role)
        self.admin_user.role = 0  # Admin role
        self.admin_user.save()
        
        self.user_token = generate_test_token()
        self.user = baker.make(User, user_id=decode_test_token(self.user_token))
        user_role = Group.objects.create(name=Roles.user.name)
        self.user.groups.add(user_role)
        self.user.role = 1  # Regular user role
        self.user.save()
        
        # Create test project
        self.project = baker.make(Project, title="Test Project")
        self.content_type = ContentType.objects.get_for_model(Project)
        
        # Create test comments
        self.approved_comment = baker.make(
            Comment,
            content_type=self.content_type,
            object_id=self.project.id,
            user=self.user,
            content="This is an approved comment",
            status='APPROVED'
        )
        
        self.pending_comment = baker.make(
            Comment,
            content_type=self.content_type,
            object_id=self.project.id,
            user=self.user,
            content="This is a pending comment",
            status='PENDING'
        )
    
    def test_create_comment_authenticated_user(self):
        """Test creating comment as authenticated user"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        
        data = {
            'content': 'This is a new comment',
            'content_type': f'{self.content_type.app_label}.{self.content_type.model}',
            'object_id': self.project.id
        }
        
        response = self.client.post(reverse('comments:comment-list'), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check comment was created
        comment = Comment.objects.get(id=response.data['id'])
        self.assertEqual(comment.content, 'This is a new comment')
        self.assertEqual(comment.user, self.user)
        self.assertEqual(comment.status, 'PENDING')  # Default status
    
    def test_create_comment_unauthenticated(self):
        """Test creating comment without authentication"""
        data = {
            'content': 'This should fail',
            'content_type': f'{self.content_type.app_label}.{self.content_type.model}',
            'object_id': self.project.id
        }
        
        response = self.client.post(reverse('comments:comment-list'), data=data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_create_reply_comment(self):
        """Test creating a reply to an existing comment"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        
        data = {
            'content': 'This is a reply',
            'content_type': f'{self.content_type.app_label}.{self.content_type.model}',
            'object_id': self.project.id,
            'parent_id': self.approved_comment.id
        }
        
        response = self.client.post(reverse('comments:comment-list'), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check reply was created correctly
        reply = Comment.objects.get(id=response.data['id'])
        self.assertEqual(reply.parent, self.approved_comment)
    
    def test_list_comments_regular_user(self):
        """Test listing comments as regular user (only approved)"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        
        response = self.client.get(
            reverse('comments:comment-list'),
            {'content_type': f'{self.content_type.app_label}.{self.content_type.model}', 
             'object_id': self.project.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only see approved comments
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], self.approved_comment.id)
    
    def test_list_comments_admin_user(self):
        """Test listing comments as admin (all comments)"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        
        response = self.client.get(
            reverse('comments:comment-list'),
            {'content_type': f'{self.content_type.app_label}.{self.content_type.model}',
             'object_id': self.project.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should see all comments
        self.assertEqual(len(response.data['results']), 2)
    
    def test_update_comment_owner(self):
        """Test updating comment by owner within time limit"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        
        data = {'content': 'Updated comment content'}
        response = self.client.patch(
            reverse('comments:comment-detail', args=[self.approved_comment.id]),
            data=data
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check comment was updated
        self.approved_comment.refresh_from_db()
        self.assertEqual(self.approved_comment.content, 'Updated comment content')
    
    def test_update_comment_non_owner(self):
        """Test updating comment by non-owner (should fail)"""
        other_user_token = generate_test_token()
        baker.make(User, user_id=decode_test_token(other_user_token))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {other_user_token}")
        
        data = {'content': 'Should not update'}
        response = self.client.patch(
            reverse('comments:comment-detail', args=[self.approved_comment.id]),
            data=data
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_delete_comment_admin(self):
        """Test deleting comment as admin"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        
        response = self.client.delete(
            reverse('comments:comment-detail', args=[self.approved_comment.id])
        )
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Comment.objects.filter(id=self.approved_comment.id).exists())
    
    def test_delete_comment_regular_user(self):
        """Test deleting comment as regular user (should fail)"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        
        response = self.client.delete(
            reverse('comments:comment-detail', args=[self.approved_comment.id])
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_react_to_comment_like(self):
        """Test adding like reaction to comment"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        
        response = self.client.post(
            reverse('comments:comment-react', args=[self.approved_comment.id]),
            {'reaction_type': 'LIKE'}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check reaction was created
        self.assertTrue(
            CommentReaction.objects.filter(
                comment=self.approved_comment,
                user=self.user,
                reaction_type='LIKE'
            ).exists()
        )
        
        # Check like count updated
        self.approved_comment.refresh_from_db()
        self.assertEqual(self.approved_comment.likes_count, 1)
    
    def test_react_to_comment_change_reaction(self):
        """Test changing reaction from like to dislike"""
        # First add a like
        baker.make(
            CommentReaction,
            comment=self.approved_comment,
            user=self.user,
            reaction_type='LIKE'
        )
        self.approved_comment.likes_count = 1
        self.approved_comment.save()
        
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        
        response = self.client.post(
            reverse('comments:comment-react', args=[self.approved_comment.id]),
            {'reaction_type': 'DISLIKE'}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check reaction was changed
        reaction = CommentReaction.objects.get(
            comment=self.approved_comment,
            user=self.user
        )
        self.assertEqual(reaction.reaction_type, 'DISLIKE')
        
        # Check counts updated
        self.approved_comment.refresh_from_db()
        self.assertEqual(self.approved_comment.likes_count, 0)
        self.assertEqual(self.approved_comment.dislikes_count, 1)
    
    def test_remove_reaction(self):
        """Test removing reaction from comment"""
        # First add a reaction
        baker.make(
            CommentReaction,
            comment=self.approved_comment,
            user=self.user,
            reaction_type='LIKE'
        )
        
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        
        response = self.client.delete(
            reverse('comments:comment-remove-reaction', args=[self.approved_comment.id])
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check reaction was removed
        self.assertFalse(
            CommentReaction.objects.filter(
                comment=self.approved_comment,
                user=self.user
            ).exists()
        )
    
    def test_approve_comment_admin(self):
        """Test approving comment as admin"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        
        response = self.client.post(
            reverse('comments:comment-approve', args=[self.pending_comment.id]),
            {'reason': 'Comment is appropriate'}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check comment was approved
        self.pending_comment.refresh_from_db()
        self.assertEqual(self.pending_comment.status, 'APPROVED')
        self.assertEqual(self.pending_comment.approved_by, self.admin_user)
        
        # Check moderation log was created
        self.assertTrue(
            CommentModerationLog.objects.filter(
                comment=self.pending_comment,
                moderator=self.admin_user,
                action='APPROVED'
            ).exists()
        )
    
    def test_approve_comment_regular_user(self):
        """Test approving comment as regular user (should fail)"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        
        response = self.client.post(
            reverse('comments:comment-approve', args=[self.pending_comment.id])
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_reject_comment_admin(self):
        """Test rejecting comment as admin"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        
        response = self.client.post(
            reverse('comments:comment-reject', args=[self.pending_comment.id]),
            {'reason': 'Inappropriate content'}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check comment was rejected
        self.pending_comment.refresh_from_db()
        self.assertEqual(self.pending_comment.status, 'REJECTED')
    
    def test_bulk_approve_comments(self):
        """Test bulk approving comments"""
        # Create more pending comments
        comment2 = baker.make(
            Comment,
            content_type=self.content_type,
            object_id=self.project.id,
            user=self.user,
            status='PENDING'
        )
        
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        
        data = {
            'comment_ids': [self.pending_comment.id, comment2.id],
            'action': 'approve',
            'reason': 'Bulk approval'
        }
        
        response = self.client.post(reverse('comments:comment-bulk-action'), data=data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check comments were approved
        self.pending_comment.refresh_from_db()
        comment2.refresh_from_db()
        
        self.assertEqual(self.pending_comment.status, 'APPROVED')
        self.assertEqual(comment2.status, 'APPROVED')
    
    def test_export_comments_admin(self):
        """Test exporting comments as CSV"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        
        response = self.client.get(
            reverse('comments:comment-export'),
            {'content_type': f'{self.content_type.app_label}.{self.content_type.model}',
             'object_id': self.project.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('attachment', response['Content-Disposition'])
    
    def test_comment_statistics(self):
        """Test getting comment statistics"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        
        response = self.client.get(
            reverse('comments:comment-statistics'),
            {'content_type': f'{self.content_type.app_label}.{self.content_type.model}',
             'object_id': self.project.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check statistics structure
        data = response.data
        self.assertIn('total', data)
        self.assertIn('approved', data)
        self.assertIn('pending', data)
        self.assertIn('rejected', data)
        self.assertIn('total_likes', data)
        self.assertIn('total_dislikes', data)
    
    def test_comment_validation_short_content(self):
        """Test comment validation for too short content"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        
        data = {
            'content': 'Hi',  # Too short
            'content_type': f'{self.content_type.app_label}.{self.content_type.model}',
            'object_id': self.project.id
        }
        
        response = self.client.post(reverse('comments:comment-list'), data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_comment_validation_invalid_content_type(self):
        """Test comment validation for invalid content type"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        
        data = {
            'content': 'This is a valid comment',
            'content_type': 'invalid.model',
            'object_id': self.project.id
        }
        
        response = self.client.post(reverse('comments:comment-list'), data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_comment_validation_nonexistent_object(self):
        """Test comment validation for non-existent object"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        
        data = {
            'content': 'This is a valid comment',
            'content_type': f'{self.content_type.app_label}.{self.content_type.model}',
            'object_id': 99999  # Non-existent ID
        }
        
        response = self.client.post(reverse('comments:comment-list'), data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class CommentModelTest(APITestCase):
    """Test Comment model methods and properties"""
    
    def setUp(self):
        self.user = baker.make(User)
        self.admin = baker.make(User)
        self.project = baker.make(Project)
        self.content_type = ContentType.objects.get_for_model(Project)
        
        self.comment = baker.make(
            Comment,
            content_type=self.content_type,
            object_id=self.project.id,
            user=self.user,
            status='PENDING'
        )
    
    def test_approve_method(self):
        """Test comment approve method"""
        self.comment.approve(self.admin)
        
        self.assertEqual(self.comment.status, 'APPROVED')
        self.assertEqual(self.comment.approved_by, self.admin)
        self.assertIsNotNone(self.comment.approved_at)
    
    def test_reject_method(self):
        """Test comment reject method"""
        self.comment.reject(self.admin)
        
        self.assertEqual(self.comment.status, 'REJECTED')
        self.assertEqual(self.comment.approved_by, self.admin)
        self.assertIsNotNone(self.comment.approved_at)
    
    def test_is_approved_property(self):
        """Test is_approved property"""
        self.assertFalse(self.comment.is_approved)
        
        self.comment.status = 'APPROVED'
        self.assertTrue(self.comment.is_approved)
    
    def test_is_pending_property(self):
        """Test is_pending property"""
        self.assertTrue(self.comment.is_pending)
        
        self.comment.status = 'APPROVED'
        self.assertFalse(self.comment.is_pending)


class CommentReactionModelTest(APITestCase):
    """Test CommentReaction model"""
    
    def setUp(self):
        self.user = baker.make(User)
        self.project = baker.make(Project)
        self.content_type = ContentType.objects.get_for_model(Project)
        
        self.comment = baker.make(
            Comment,
            content_type=self.content_type,
            object_id=self.project.id,
            user=self.user,
            likes_count=0,
            dislikes_count=0
        )
    
    def test_create_like_reaction(self):
        """Test creating like reaction updates counter"""
        reaction = CommentReaction.objects.create(
            comment=self.comment,
            user=self.user,
            reaction_type='LIKE'
        )
        
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.likes_count, 1)
        self.assertEqual(self.comment.dislikes_count, 0)
    
    def test_change_reaction_type(self):
        """Test changing reaction type updates counters"""
        reaction = CommentReaction.objects.create(
            comment=self.comment,
            user=self.user,
            reaction_type='LIKE'
        )
        
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.likes_count, 1)
        
        # Change to dislike
        reaction.reaction_type = 'DISLIKE'
        reaction.save()
        
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.likes_count, 0)
        self.assertEqual(self.comment.dislikes_count, 1)
    
    def test_delete_reaction(self):
        """Test deleting reaction updates counter"""
        reaction = CommentReaction.objects.create(
            comment=self.comment,
            user=self.user,
            reaction_type='LIKE'
        )
        
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.likes_count, 1)
        
        # Delete reaction
        reaction.delete()
        
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.likes_count, 0)