from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Project, Requirement, Task, ProjectModule
from notes.models import KnowledgeBaseNote
from files.models import ProjectFile

User = get_user_model()


class TasksModelTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpassword"
        )

    def test_project_id_generation(self):
        project1 = Project.objects.create(
            name="Solar Transition Control", created_by=self.user
        )
        self.assertTrue(project1.project_id.startswith("PRJ-STC-"))
        self.assertTrue(project1.project_id.endswith("-0001"))

        project2 = Project.objects.create(
            name="Controller System", created_by=self.user
        )
        self.assertTrue(project2.project_id.startswith("PRJ-CS-"))
        self.assertTrue(project2.project_id.endswith("-0002"))

    def test_requirement_id_generation(self):
        project = Project.objects.create(
            name="Solar Transition Control", created_by=self.user
        )
        req1 = Requirement.objects.create(project=project, name="First Requirement")
        self.assertTrue(req1.req_id.startswith("REQ-STC-"))
        self.assertTrue(req1.req_id.endswith("-0001"))

        req2 = Requirement.objects.create(project=project, name="Second Requirement")
        self.assertTrue(req2.req_id.startswith("REQ-STC-"))
        self.assertTrue(req2.req_id.endswith("-0002"))

    def test_task_id_generation(self):
        project = Project.objects.create(
            name="Solar Transition Control", created_by=self.user
        )
        module = ProjectModule.objects.create(project=project, name="Test Module")
        task1 = Task.objects.create(
            project=project, module=module, title="First Task", created_by=self.user
        )
        self.assertTrue(task1.task_id.startswith("TAS-STC-"))
        self.assertTrue(task1.task_id.endswith("-0001"))

    def test_knowledge_base_note_sync(self):
        project = Project.objects.create(name="Test Project", created_by=self.user)
        note = KnowledgeBaseNote.objects.create(
            project=project,
            title="Test Note",
            content="This is a test content.",
            author=self.user,
        )

        # Verify a ProjectFile was created with the correct category and name
        self.assertTrue(
            ProjectFile.objects.filter(
                project=project, original_name="Test Note.md"
            ).exists()
        )

        pf = ProjectFile.objects.get(project=project, original_name="Test Note.md")
        self.assertEqual(pf.category.name, "Notes")

        # Test updating the note
        note.content = "Updated content."
        note.save()

        pf.refresh_from_db()
        self.assertTrue(pf.file.read().decode("utf-8") == "Updated content.")

    def test_file_category_recursive_rename(self):
        from files.models import FileCategory, ProjectFile
        from django.core.files.base import ContentFile
        import os

        project = Project.objects.create(name="Test Folder Sync Project", created_by=self.user)
        # Create parent category
        parent_cat = FileCategory.objects.create(
            name="ParentFolder",
            project=project,
            created_by=self.user
        )
        # Create child category
        child_cat = FileCategory.objects.create(
            name="ChildFolder",
            project=project,
            parent=parent_cat,
            created_by=self.user
        )
        # Create file in child category
        pf = ProjectFile.objects.create(
            project=project,
            category=child_cat,
            uploaded_by=self.user,
            original_name="nested_file.txt",
        )
        pf.file.save("nested_file.txt", ContentFile(b"Nested file content"), save=False)
        pf.save()

        # Check initial path
        pf.refresh_from_db()
        project_id = project.project_id or f"PRJ-{project.pk}"
        expected_initial_path = os.path.join("projects", project_id, "ParentFolder", "ChildFolder", "nested_file.txt")
        self.assertEqual(pf.file.name.replace("\\", "/"), expected_initial_path.replace("\\", "/"))

        # Rename parent category
        parent_cat.name = "RenamedParent"
        parent_cat.save()

        # Check if grandchild file path in DB is updated correctly
        pf.refresh_from_db()
        expected_new_path = os.path.join("projects", project_id, "RenamedParent", "ChildFolder", "nested_file.txt")
        self.assertEqual(pf.file.name.replace("\\", "/"), expected_new_path.replace("\\", "/"))


class TasksViewsTestCase(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="testpassword",
            role="admin",
        )
        self.pm_user = User.objects.create_user(
            username="pmuser", email="pm@example.com", password="testpassword"
        )
        self.member_user = User.objects.create_user(
            username="memberuser", email="member@example.com", password="testpassword"
        )

        self.project = Project.objects.create(
            name="Test Project", created_by=self.admin_user
        )
        self.project.managers.add(self.pm_user)
        self.project.members.add(self.member_user)

        self.module = ProjectModule.objects.create(
            project=self.project, name="Test Module"
        )
        self.task = Task.objects.create(
            project=self.project,
            module=self.module,
            title="Test Task",
            created_by=self.admin_user,
            status="todo",
        )
        self.task.assignees.add(self.member_user)

        self.client = Client()

    def test_task_update_status_as_pm(self):
        self.client.login(username="pmuser", password="testpassword")
        url = reverse("tasks:task_update_status", args=[self.task.pk])
        response = self.client.post(
            url, data={"status": "in_progress"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)

        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "in_progress")

    def test_task_update_status_as_admin(self):
        self.client.login(username="admin", password="testpassword")
        url = reverse("tasks:task_update_status", args=[self.task.pk])
        response = self.client.post(
            url, data={"status": "done"}, content_type="application/json"
        )
        print("ADMIN TEST RESPONSE:", response.content)
        self.assertEqual(response.status_code, 200)

        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "done")

    def test_task_update_status_as_member_denied(self):
        self.client.login(username="memberuser", password="testpassword")
        url = reverse("tasks:task_update_status", args=[self.task.pk])
        response = self.client.post(
            url, data={"status": "done"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 403)

        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "todo")

    def test_project_list_view(self):
        self.client.login(username="memberuser", password="testpassword")
        response = self.client.get(reverse("tasks:project_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Project")

    def test_task_detail_view(self):
        self.client.login(username="memberuser", password="testpassword")
        response = self.client.get(reverse("tasks:task_detail", args=[self.task.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Task")

    def test_master_report_md_download(self):
        self.client.login(username="admin", password="testpassword")
        url = reverse("tasks:master_report", args=[self.project.pk])
        response = self.client.get(url + "?format=md")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/markdown')
        self.assertTrue(b"# Project Master Dossier:" in response.content)

    def test_master_report_docx_download(self):
        self.client.login(username="admin", password="testpassword")
        url = reverse("tasks:master_report", args=[self.project.pk])
        response = self.client.get(url + "?format=docx")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')

    def test_master_report_xlsx_download(self):
        self.client.login(username="admin", password="testpassword")
        url = reverse("tasks:master_report", args=[self.project.pk])
        response = self.client.get(url + "?format=xlsx")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
