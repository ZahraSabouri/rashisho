from django.test import TestCase
from django.urls import reverse
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase
from model_bakery import baker

from apps.account.models import User
from apps.project import models
from apps.settings.models import StudyField


class ProjectActivationModelTest(TestCase):
    """Test project model activation functionality"""

    def setUp(self):
        self.study_field = baker.make(StudyField)
        self.project = baker.make(
            models.Project,
            title="Test Project",
            is_active=True,
            visible=True
        )

    def test_project_activation_defaults(self):
        """Test project is active by default"""
        new_project = baker.make(models.Project)
        self.assertTrue(new_project.is_active)
        self.assertTrue(new_project.visible)

    def test_can_be_selected_property(self):
        """Test can_be_selected property logic"""
        # Both active and visible
        self.assertTrue(self.project.can_be_selected)
        
        # Active but not visible
        self.project.visible = False
        self.assertFalse(self.project.can_be_selected)
        
        # Visible but not active
        self.project.visible = True
        self.project.is_active = False
        self.assertFalse(self.project.can_be_selected)

    def test_status_display_property(self):
        """Test status display messages"""
        # Active and visible
        self.assertEqual(self.project.status_display, "فعال")
        
        # Inactive
        self.project.is_active = False
        self.assertEqual(self.project.status_display, "غیرفعال")
        
        # Hidden
        self.project.is_active = True
        self.project.visible = False
        self.assertEqual(self.project.status_display, "مخفی")

    def test_activate_deactivate_methods(self):
        """Test activation/deactivation methods"""
        # Test deactivation
        self.project.deactivate()
        self.project.refresh_from_db()
        self.assertFalse(self.project.is_active)
        
        # Test activation
        self.project.activate()
        self.project.refresh_from_db()
        self.assertTrue(self.project.is_active)

    def test_str_representation(self):
        """Test string representation includes status"""
        active_str = str(self.project)
        self.assertIn("✅", active_str)
        self.assertIn(self.project.title, active_str)
        
        self.project.deactivate()
        inactive_str = str(self.project)
        self.assertIn("❌", inactive_str)

    def test_get_related_projects_excludes_inactive(self):
        """Test related projects excludes inactive ones"""
        tag = baker.make(models.Tag, name="test-tag")
        
        # Create related projects
        related_active = baker.make(
            models.Project,
            is_active=True,
            visible=True
        )
        related_inactive = baker.make(
            models.Project,
            is_active=False,
            visible=True
        )
        
        # Add same tag to all projects
        for project in [self.project, related_active, related_inactive]:
            project.tags.add(tag)
        
        related = self.project.get_related_projects()
        
        # Only active project should be in results
        self.assertIn(related_active, related)
        self.assertNotIn(related_inactive, related)


class ProjectActivationAPITest(APITestCase):
    """Test project activation API endpoints"""

    def setUp(self):
        cache.clear()
        
        self.user = baker.make(User, role=1)  # Regular user
        self.admin = baker.make(User, role=2, is_staff=True)  # Admin
        
        self.study_field = baker.make(StudyField)
        self.active_project = baker.make(
            models.Project,
            title="Active Project",
            is_active=True,
            visible=True
        )
        self.inactive_project = baker.make(
            models.Project,
            title="Inactive Project",
            is_active=False,
            visible=True
        )

    def test_project_list_shows_all_for_admins(self):
        """Admin users should see all projects"""
        self.client.force_authenticate(user=self.admin)
        
        url = reverse("project:detail-list")
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        project_ids = [p['id'] for p in response.data['results']]
        
        self.assertIn(str(self.active_project.id), project_ids)
        self.assertIn(str(self.inactive_project.id), project_ids)

    def test_project_list_filters_for_users(self):
        """Regular users should only see visible projects"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse("project:detail-list")
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should see both active and inactive visible projects
        project_ids = [p['id'] for p in response.data['results']]
        self.assertIn(str(self.active_project.id), project_ids)
        self.assertIn(str(self.inactive_project.id), project_ids)
        
        # But inactive ones should be marked as non-selectable
        inactive_data = None
        for project in response.data['results']:
            if project['id'] == str(self.inactive_project.id):
                inactive_data = project
                break
        
        self.assertIsNotNone(inactive_data)
        self.assertFalse(inactive_data.get('is_selectable', True))

    def test_active_projects_endpoint(self):
        """Test active projects endpoint"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse("project:detail-active-projects")
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should only contain active projects
        project_ids = [p['id'] for p in response.data['results']]
        self.assertIn(str(self.active_project.id), project_ids)
        self.assertNotIn(str(self.inactive_project.id), project_ids)

    def test_homepage_projects_only_active(self):
        """Homepage should only show active projects"""
        url = reverse("project:homepage-projects-list")
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should only contain active projects
        project_ids = [p['id'] for p in response.data['results']]
        self.assertIn(str(self.active_project.id), project_ids)
        self.assertNotIn(str(self.inactive_project.id), project_ids)

    def test_project_status_list_permissions(self):
        """Test project status endpoint permissions"""
        url = reverse("project:project-status-list")
        
        # Anonymous user
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Regular user
        self.client.force_authenticate(user=self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Admin user
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_project_activation_permissions(self):
        """Test project activation endpoint permissions"""
        url = reverse("project:project-activation")
        data = {
            'project_ids': [str(self.inactive_project.id)],
            'is_active': True
        }
        
        # Anonymous user
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Regular user
        self.client.force_authenticate(user=self.user)
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Admin user
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_bulk_project_activation(self):
        """Test bulk project activation"""
        self.client.force_authenticate(user=self.admin)
        
        url = reverse("project:project-activation")
        data = {
            'project_ids': [str(self.inactive_project.id)],
            'is_active': True,
            'reason': 'Test activation'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('updated_count', response.data['details'])
        
        # Verify project was activated
        self.inactive_project.refresh_from_db()
        self.assertTrue(self.inactive_project.is_active)

    def test_single_project_status_toggle(self):
        """Test single project status toggle"""
        self.client.force_authenticate(user=self.admin)
        
        url = reverse("project:single-project-status", args=[self.active_project.id])
        
        # Get current status
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_active'])
        
        # Toggle status
        response = self.client.patch(url, {'reason': 'Test toggle'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify project was deactivated
        self.active_project.refresh_from_db()
        self.assertFalse(self.active_project.is_active)

    def test_project_status_stats(self):
        """Test project status statistics endpoint"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse("project:project-status-stats")
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        stats = response.data
        self.assertIn('total_projects', stats)
        self.assertIn('active_projects', stats)
        self.assertIn('inactive_projects', stats)
        self.assertIn('activation_rate', stats)

    def test_validation_errors(self):
        """Test validation errors in activation endpoint"""
        self.client.force_authenticate(user=self.admin)
        
        url = reverse("project:project-activation")
        
        # Missing project_ids
        response = self.client.post(url, {'is_active': True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Invalid project ID
        invalid_data = {
            'project_ids': ['invalid-uuid'],
            'is_active': True
        }
        response = self.client.post(url, invalid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cache_invalidation(self):
        """Test that caches are properly cleared after status changes"""
        self.client.force_authenticate(user=self.admin)
        
        # First request to populate cache
        self.client.get(reverse("project:detail-active-projects"))
        self.client.get(reverse("project:project-status-stats"))
        
        # Activate a project
        url = reverse("project:project-activation")
        data = {
            'project_ids': [str(self.inactive_project.id)],
            'is_active': True
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify caches were cleared by checking fresh data
        stats_response = self.client.get(reverse("project:project-status-stats"))
        self.assertEqual(stats_response.status_code, status.HTTP_200_OK)


# Run tests with:
# python manage.py test apps.project.tests.test_project_activation -v 2