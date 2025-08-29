from django.urls import reverse
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase
from model_bakery import baker

from apps.project import models
from apps.account.models import User
from apps.settings.models import StudyField


class TestTagViewSet(APITestCase):
    """Test tag CRUD operations and permissions"""

    def setUp(self):
        """Set up test data"""
        # Create users with different roles
        self.admin_user = baker.make(User, role=2, is_staff=True)  # Admin
        self.regular_user = baker.make(User, role=1)  # Regular user
        
        # Create some test tags
        self.tag1 = baker.make(models.Tag, name="python", description="Python programming language")
        self.tag2 = baker.make(models.Tag, name="django", description="Django web framework")
        self.tag3 = baker.make(models.Tag, name="machine-learning", description="ML and AI")
        
        # Create study field for projects
        self.study_field = baker.make(StudyField)
        
        # Clear cache before each test
        cache.clear()

    def test_list_tags_unauthenticated(self):
        """Unauthenticated users should be able to list tags"""
        url = reverse("project:tags-list")
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 3)

    def test_list_tags_with_search(self):
        """Test tag search functionality"""
        url = reverse("project:tags-list")
        response = self.client.get(url, {"search": "python"})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], "python")

    def test_create_tag_as_admin(self):
        """Admins should be able to create tags"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("project:tags-list")
        
        data = {
            "name": "react",
            "description": "React.js library for UI development"
        }
        
        response = self.client.post(url, data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertEqual(response.data['tag']['name'], "react")
        
        # Verify tag was created in database
        self.assertTrue(models.Tag.objects.filter(name="react").exists())

    def test_create_tag_as_regular_user(self):
        """Regular users should not be able to create tags"""
        self.client.force_authenticate(user=self.regular_user)
        url = reverse("project:tags-list")
        
        data = {
            "name": "react",
            "description": "React.js library"
        }
        
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_tag_validation(self):
        """Test tag name validation"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("project:tags-list")
        
        # Test too short name
        data = {"name": "a", "description": "Too short"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Test duplicate name
        data = {"name": "python", "description": "Duplicate name"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_tag_as_admin(self):
        """Admins should be able to update tags"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("project:tags-detail", args=[self.tag1.id])
        
        data = {
            "name": "python-updated",
            "description": "Updated Python description"
        }
        
        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify update in database
        self.tag1.refresh_from_db()
        self.assertEqual(self.tag1.name, "python-updated")

    def test_delete_tag_unused(self):
        """Admins should be able to delete unused tags"""
        # Create an unused tag
        unused_tag = baker.make(models.Tag, name="unused")
        
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("project:tags-detail", args=[unused_tag.id])
        
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        
        # Verify tag was deleted
        self.assertFalse(models.Tag.objects.filter(id=unused_tag.id).exists())

    def test_delete_tag_in_use(self):
        """Should not be able to delete tags that are in use"""
        # Create a project with this tag
        project = baker.make(models.Project, visible=True)
        project.tags.add(self.tag1)
        
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("project:tags-detail", args=[self.tag1.id])
        
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_popular_tags_endpoint(self):
        """Test the popular tags endpoint"""
        # Create projects with tags
        project1 = baker.make(models.Project, visible=True)
        project2 = baker.make(models.Project, visible=True)
        
        project1.tags.add(self.tag1, self.tag2)  # python, django
        project2.tags.add(self.tag1)  # python
        # tag1 (python) should be most popular with 2 projects
        
        url = reverse("project:tags-popular")
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('popular_tags', response.data)
        self.assertIn('count', response.data)
        
        # Python should be first (most popular)
        if response.data['popular_tags']:
            first_tag = response.data['popular_tags'][0]
            self.assertEqual(first_tag['name'], 'python')

    def test_unused_tags_endpoint(self):
        """Test the unused tags endpoint (admin only)"""
        # Create an unused tag
        unused_tag = baker.make(models.Tag, name="unused")
        
        # Test as admin
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("project:tags-unused")
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test as regular user
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class TestProjectTagManagement(APITestCase):
    """Test project-tag relationship management"""

    def setUp(self):
        self.admin_user = baker.make(User, role=2, is_staff=True)
        self.regular_user = baker.make(User, role=1)
        
        self.project = baker.make(models.Project, title="Test Project", visible=True)
        self.tag1 = baker.make(models.Tag, name="python")
        self.tag2 = baker.make(models.Tag, name="django")
        self.tag3 = baker.make(models.Tag, name="api")
        
        cache.clear()

    def test_get_project_tags(self):
        """Anyone should be able to get project tags"""
        self.project.tags.add(self.tag1, self.tag2)
        
        url = reverse("project:project-tags", args=[self.project.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['tags']), 2)
        self.assertEqual(response.data['project_title'], "Test Project")

    def test_add_tags_to_project_as_admin(self):
        """Admins should be able to add tags to projects"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("project:project-tags", args=[self.project.id])
        
        data = {
            "tag_ids": [str(self.tag1.id), str(self.tag2.id)]
        }
        
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        
        # Verify tags were added
        self.project.refresh_from_db()
        self.assertEqual(self.project.tags.count(), 2)
        self.assertTrue(self.project.tags.filter(id=self.tag1.id).exists())

    def test_add_tags_to_project_as_regular_user(self):
        """Regular users should not be able to add tags to projects"""
        self.client.force_authenticate(user=self.regular_user)
        url = reverse("project:project-tags", args=[self.project.id])
        
        data = {
            "tag_ids": [str(self.tag1.id)]
        }
        
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_clear_project_tags(self):
        """Test clearing all project tags"""
        self.project.tags.add(self.tag1, self.tag2)
        
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("project:project-tags", args=[self.project.id])
        
        data = {"tag_ids": []}
        
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify tags were cleared
        self.project.refresh_from_db()
        self.assertEqual(self.project.tags.count(), 0)

    def test_add_invalid_tags_to_project(self):
        """Should handle invalid tag IDs gracefully"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("project:project-tags", args=[self.project.id])
        
        data = {
            "tag_ids": ["00000000-0000-0000-0000-000000000000"]  # Non-existent tag
        }
        
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nonexistent_project(self):
        """Should return 404 for non-existent project"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("project:project-tags", args=["00000000-0000-0000-0000-000000000000"])
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TestRelatedProjects(APITestCase):
    """Test related project suggestions based on tags"""

    def setUp(self):
        self.user = baker.make(User, role=1)
        
        # Create projects
        self.project1 = baker.make(models.Project, title="Python Web App", visible=True)
        self.project2 = baker.make(models.Project, title="Django API", visible=True)
        self.project3 = baker.make(models.Project, title="React Frontend", visible=True)
        self.project4 = baker.make(models.Project, title="ML Model", visible=True)
        self.project5 = baker.make(models.Project, title="Hidden Project", visible=False)
        
        # Create tags
        self.tag_python = baker.make(models.Tag, name="python")
        self.tag_django = baker.make(models.Tag, name="django")
        self.tag_web = baker.make(models.Tag, name="web")
        self.tag_ml = baker.make(models.Tag, name="machine-learning")
        self.tag_react = baker.make(models.Tag, name="react")
        
        # Set up tag relationships
        self.project1.tags.add(self.tag_python, self.tag_django, self.tag_web)  # 3 tags
        self.project2.tags.add(self.tag_python, self.tag_django)  # 2 matching with project1
        self.project3.tags.add(self.tag_web, self.tag_react)  # 1 matching with project1
        self.project4.tags.add(self.tag_python, self.tag_ml)  # 1 matching with project1
        self.project5.tags.add(self.tag_python)  # Hidden project (should not appear)
        
        cache.clear()

    def test_get_related_projects_authenticated(self):
        """Authenticated users should be able to get related projects"""
        self.client.force_authenticate(user=self.user)
        url = reverse("project:related-projects", args=[self.project1.id])
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check response structure
        self.assertIn('project_id', response.data)
        self.assertIn('project_title', response.data)
        self.assertIn('related_projects', response.data)
        self.assertIn('related_count', response.data)
        
        # Verify we get related projects
        related = response.data['related_projects']
        self.assertTrue(len(related) > 0)
        
        # project2 should be most related (shares python+django)
        # project4 and project3 should follow (1 shared tag each)
        # project5 should not appear (hidden)
        
        related_ids = [p['id'] for p in related]
        self.assertIn(str(self.project2.id), related_ids)
        self.assertNotIn(str(self.project5.id), related_ids)  # Hidden project

    def test_get_related_projects_unauthenticated(self):
        """Unauthenticated users should not access related projects"""
        url = reverse("project:related-projects", args=[self.project1.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_related_projects_ordering(self):
        """Related projects should be ordered by shared tag count"""
        self.client.force_authenticate(user=self.user)
        url = reverse("project:related-projects", args=[self.project1.id])
        
        response = self.client.get(url)
        related = response.data['related_projects']
        
        if len(related) >= 2:
            # First project should have higher shared_tags_count than second
            self.assertGreaterEqual(
                related[0]['shared_tags_count'],
                related[1]['shared_tags_count']
            )

    def test_project_without_tags_has_no_related_projects(self):
        """Projects without tags should have no related projects"""
        project_no_tags = baker.make(models.Project, title="No Tags Project", visible=True)
        
        self.client.force_authenticate(user=self.user)
        url = reverse("project:related-projects", args=[project_no_tags.id])
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['related_projects']), 0)

    def test_hidden_project_not_found(self):
        """Hidden projects should return 404"""
        self.client.force_authenticate(user=self.user)
        url = reverse("project:related-projects", args=[self.project5.id])
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_nonexistent_project(self):
        """Non-existent projects should return 404"""
        self.client.force_authenticate(user=self.user)
        url = reverse("project:related-projects", args=["00000000-0000-0000-0000-000000000000"])
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_related_projects_cache(self):
        """Test that related projects are cached"""
        self.client.force_authenticate(user=self.user)
        url = reverse("project:related-projects", args=[self.project1.id])
        
        # First request
        response1 = self.client.get(url)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        
        # Second request should hit cache
        response2 = self.client.get(url)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(response1.data, response2.data)


class TestTagIntegration(APITestCase):
    """Integration tests for tags with project serializers"""

    def setUp(self):
        self.user = baker.make(User, role=1)
        self.admin_user = baker.make(User, role=2, is_staff=True)
        
        self.study_field = baker.make(StudyField)
        self.project = baker.make(models.Project, visible=True)
        self.tag1 = baker.make(models.Tag, name="integration")
        self.tag2 = baker.make(models.Tag, name="testing")
        
        self.project.tags.add(self.tag1, self.tag2)
        self.project.study_fields.add(self.study_field)

    def test_project_list_includes_tags(self):
        """Project list endpoints should include tag information"""
        url = reverse("project:detail-list")
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Find our project in results
        project_data = None
        for project in response.data['results']:
            if project['id'] == str(self.project.id):
                project_data = project
                break
        
        self.assertIsNotNone(project_data)
        self.assertIn('tags', project_data)
        self.assertIn('tags_count', project_data)
        self.assertEqual(len(project_data['tags']), 2)

    def test_project_detail_includes_tags(self):
        """Project detail endpoint should include tag information"""
        url = reverse("project:detail-detail", args=[self.project.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('tags', response.data)
        self.assertEqual(len(response.data['tags']), 2)

# Run tests with:
# python manage.py test apps.project.tests.test_tags