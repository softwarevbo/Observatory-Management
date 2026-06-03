"""
Management command to seed the database with initial demo data.
Run: python manage.py seed_data
"""

import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from django.db.models.signals import post_save, post_delete

from accounts.models import User
from tasks.models import Project, Requirement, Task
from testcases.models import TestCase
from bugs.models import BugReport
from events.models import CalendarEvent
from notifications.models import Notification
from tasks.signals import audit_post_save, audit_post_delete, add_task_module_members


class Command(BaseCommand):
    help = "Seed the database with demo data for IIAP OM"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING("Flushing existing records and seeding database with transaction block..."))

        # ── DISCONNECT SIGNALS TO SPEED UP SEEDING ────────────────────────────
        post_save.disconnect(audit_post_save, sender=Project)
        post_save.disconnect(audit_post_save, sender=Requirement)
        post_save.disconnect(audit_post_save, sender=Task)
        post_save.disconnect(audit_post_save, sender=TestCase)
        post_save.disconnect(audit_post_save, sender=BugReport)
        
        post_delete.disconnect(audit_post_delete, sender=Project)
        post_delete.disconnect(audit_post_delete, sender=Requirement)
        post_delete.disconnect(audit_post_delete, sender=Task)
        post_delete.disconnect(audit_post_delete, sender=TestCase)
        post_delete.disconnect(audit_post_delete, sender=BugReport)

        post_save.disconnect(add_task_module_members, sender=Task)

        with transaction.atomic():
            # ── FLUSH EXISTING DATA ───────────────────────────────────────────
            User.objects.exclude(is_superuser=True).delete()
            Project.objects.all().delete()
            Requirement.objects.all().delete()
            Task.objects.all().delete()
            TestCase.objects.all().delete()
            BugReport.objects.all().delete()
            CalendarEvent.objects.all().delete()
            Notification.objects.all().delete()

            # Get or create admin — always ensure correct state
            admin, created = User.objects.get_or_create(
                username="admin",
                defaults={
                    "first_name": "System",
                    "last_name": "Administrator",
                    "email": "admin@iiap.io",
                    "role": "admin",
                    "team": "general",
                    "designation": "System Administrator",
                    "avatar_color": "#ef4444",
                    "is_staff": True,
                    "is_superuser": True,
                    "is_active": True,
                }
            )
            # Always update admin fields to ensure consistency
            admin.role = "admin"
            admin.is_staff = True
            admin.is_superuser = True
            admin.is_active = True
            admin.set_password("nexuspm123")
            admin.save()
            self.stdout.write(f"  {'Created' if created else 'Updated'} superuser: admin / nexuspm123")

            # ── CREATE 20 USERS ───────────────────────────────────────────────
            teams = ["electronics", "software", "mechanical", "optics", "simulation"]
            first_names = [
                "Rajesh", "Sara", "Arjun", "Priya", "Vikram", "Ananya", "Suresh", "Neha", "Amit", "Kiran",
                "Sunita", "Deepak", "Rohan", "Meera", "Vijay", "Asha", "Sanjay", "Divya", "Alok", "Pooja"
            ]
            last_names = [
                "Kumar", "Nair", "Sharma", "Menon", "Pillai", "Reddy", "Babu", "Gupta", "Patel", "Joshi",
                "Rao", "Singh", "Das", "Iyer", "Varma", "Nair", "Sen", "Bose", "Choudhury", "Mishra"
            ]

            pm_users = []
            member_users = []

            for i in range(19):
                role = "project_manager" if i < 5 else "member"
                team = teams[i % len(teams)]
                first_name = first_names[i]
                last_name = last_names[i]
                username = f"user_{i+1}"
                
                user = User.objects.create(
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    email=f"{username}@iiap.io",
                    role=role,
                    team=team,
                    designation=f"{team.capitalize()} {'Project Manager' if role == 'project_manager' else 'Engineer'}",
                    avatar_color=f"#{random.randint(0x100000, 0xFFFFFF):06x}"
                )
                user.set_password("nexuspm123")
                user.save()
                
                if role == "project_manager":
                    pm_users.append(user)
                else:
                    member_users.append(user)
                    
                self.stdout.write(f"  Created user: {user.username} ({user.get_role_display()})")

            # Fallback list validation
            if not pm_users:
                pm_users = [admin]
            if not member_users:
                member_users = [admin]

            # ── CREATE 20 PROJECTS ────────────────────────────────────────────
            today = date.today()
            status_choices = ["planning", "active", "on_hold", "completed"]
            priority_choices = ["low", "medium", "high", "critical"]
            
            project_names = [
                "Controller Development for 30-inch Telescope",
                "Optical Alignment Module v1.2",
                "PCB Design and Power Optimization",
                "Firmware OTA Update Framework",
                "Enclosure Thermal Analysis & Simulation",
                "System Simulation and HIL Testing",
                "Laser Interferometer Precision Mount",
                "Spectrograph Mechanical Housing",
                "CCD Cooling Controller System",
                "Data Acquisition Pipeline Software",
                "Atmospheric Dispersion Corrector",
                "Guidestar Tracking Servo Control",
                "Dome Shutter Mechanical Driver",
                "Telescope Control UI Console",
                "Cryogenic Vessel Vacuum Monitor",
                "Primary Mirror Active Support Simulator",
                "Secondary Mirror Position Controller",
                "High-Speed Wavefront Sensor",
                "Fiber Injector Positioning System",
                "Real-Time Adaptive Optics Pipeline"
            ]

            created_projects = []
            for i, name in enumerate(project_names):
                module = teams[i % len(teams)]
                status = status_choices[i % len(status_choices)]
                priority = priority_choices[i % len(priority_choices)]
                manager = pm_users[i % len(pm_users)]
                
                project = Project.objects.create(
                    name=name,
                    description=f"Comprehensive development dossier, design specifications, and validation routines for {name}.",
                    module=module,
                    status=status,
                    priority=priority,
                    start_date=today - timedelta(days=20 + i),
                    end_date=today + timedelta(days=30 + i * 2),
                    created_by=admin,
                    project_incharge=manager,
                )
                project.managers.add(manager)
                
                # Add some members
                project.members.add(manager)
                project.members.add(member_users[i % len(member_users)])
                project.members.add(member_users[(i + 1) % len(member_users)])
                
                created_projects.append(project)
                self.stdout.write(f"  Created project: {project.name}")

            # ── SEED REQUIREMENTS, TASKS, AND TEST CASES PER PROJECT ──────────
            req_types = ["business", "functional", "technical", "security", "non_functional"]
            req_statuses = ["draft", "review", "approved", "implemented", "verified"]
            task_types = ["task", "bug", "feature", "research"]
            task_statuses = ["todo", "in_progress", "review", "done"]
            tc_statuses = ["pending", "passed", "failed", "blocked"]
            bug_statuses = ["open", "in_progress", "resolved", "closed"]
            event_types = ["meeting", "milestone", "review"]

            for p_idx, project in enumerate(created_projects):
                self.stdout.write(self.style.HTTP_INFO(f"Seeding items for project: {project.name}..."))
                
                # 1. Create 20 Requirements for this project
                project_reqs = []
                for r_idx in range(20):
                    req = Requirement.objects.create(
                        project=project,
                        name=f"Requirement {r_idx + 1:02d} for {project.name}",
                        description=f"Detailed requirement criteria defining constraint {r_idx + 1} for {project.name}.",
                        requirement_type=req_types[r_idx % len(req_types)],
                        priority=priority_choices[r_idx % len(priority_choices)],
                        status=req_statuses[r_idx % len(req_statuses)],
                        created_by=admin
                    )
                    project_reqs.append(req)

                # Link consecutive requirements as dependencies
                for r_idx in range(1, 20):
                    project_reqs[r_idx].dependencies.add(project_reqs[r_idx - 1])

                # 2. Create 12 Parent Tasks for this project (Approved by default)
                parent_tasks = []
                for t_idx in range(12):
                    requirement = project_reqs[t_idx % len(project_reqs)]
                    manager = pm_users[t_idx % len(pm_users)]
                    assignee = member_users[t_idx % len(member_users)]
                    
                    task = Task(
                        title=f"Parent Task {t_idx + 1:02d} for {project.name}",
                        project=project,
                        requirement=requirement,
                        status=task_statuses[t_idx % len(task_statuses)],
                        priority=priority_choices[t_idx % len(priority_choices)],
                        task_type=task_types[t_idx % len(task_types)],
                        created_by=manager,
                        is_approved=True,  # Approval bypass for seed visibility
                        due_date=today + timedelta(days=5 + t_idx),
                        estimated_hours=10 + t_idx
                    )
                    task._skip_progress_update = True
                    task.save()
                    task.assignees.add(assignee)
                    parent_tasks.append(task)

                # 3. Create 10 Subtasks for this project (linked to parent tasks, Approved by default)
                sub_tasks = []
                for st_idx in range(10):
                    parent_task = parent_tasks[st_idx % len(parent_tasks)]
                    requirement = project_reqs[(st_idx + 12) % len(project_reqs)]
                    manager = pm_users[(st_idx + 1) % len(pm_users)]
                    assignee = member_users[(st_idx + 1) % len(member_users)]
                    
                    subtask = Task(
                        title=f"Subtask {st_idx + 1:02d} under {parent_task.task_id} for {project.name}",
                        project=project,
                        requirement=requirement,
                        parent_task=parent_task,
                        status=task_statuses[(st_idx + 1) % len(task_statuses)],
                        priority=priority_choices[(st_idx + 1) % len(priority_choices)],
                        task_type=task_types[(st_idx + 1) % len(task_types)],
                        created_by=manager,
                        is_approved=True,  # Approval bypass for seed visibility
                        due_date=today + timedelta(days=7 + st_idx),
                        estimated_hours=5 + st_idx
                    )
                    subtask._skip_progress_update = True
                    subtask.save()
                    subtask.assignees.add(assignee)
                    sub_tasks.append(subtask)

                # 4. Create 1 Test Case for each Task (12 Parent + 10 Subtasks = 22 total, Approved by default)
                all_tasks = parent_tasks + sub_tasks
                for tc_idx, task in enumerate(all_tasks):
                    TestCase.objects.create(
                        project=project,
                        task=task,
                        title=f"Verification scenario for {task.title}",
                        scenario=f"Validate inputs and constraints as per specifications for {project.name}.",
                        preconditions="System fully powered, environmental chambers stabilized.",
                        steps="1. Run setup scripts\n2. Trigger target sequence\n3. Capture output metrics",
                        expected_result=f"System behaviour complies with {project.name} design rules.",
                        priority=priority_choices[tc_idx % len(priority_choices)],
                        status=tc_statuses[tc_idx % len(tc_statuses)],
                        approval_status="approved",  # Seed as approved to be visible
                        created_by=admin
                    )

                # 5. Create 5 Bug Reports for this project
                for b_idx in range(5):
                    reporter = member_users[b_idx % len(member_users)]
                    bug = BugReport.objects.create(
                        title=f"Bug {b_idx + 1:02d} in {project.name} subsystem",
                        project=project,
                        reported_by=reporter,
                        severity=priority_choices[b_idx % len(priority_choices)],
                        status=bug_statuses[b_idx % len(bug_statuses)],
                        description=f"Observed unexpected signal drift or performance drop in {project.name} modules.",
                        steps_to_reproduce="1. Initialize module\n2. Run continuously for 4 hours\n3. Observe readings log",
                        expected_behavior="Baseline reading within tolerance bands.",
                        actual_behavior="Drift exceeds safety limits."
                    )
                    bug.assignees.add(reporter)

                # 6. Create 3 Calendar Events for this project
                for e_idx in range(3):
                    manager = pm_users[e_idx % len(pm_users)]
                    CalendarEvent.objects.create(
                        title=f"Milestone {e_idx + 1:02d} for {project.name}",
                        event_type=event_types[e_idx % len(event_types)],
                        project=project,
                        start_datetime=timezone.now() + timedelta(days=e_idx + 1),
                        end_datetime=timezone.now() + timedelta(days=e_idx + 1, hours=2),
                        created_by=manager,
                        color="#4f8ef7",
                        description=f"Comprehensive milestone review for {project.name} design deliverables."
                    )

                # 7. Create 5 Notifications for this project
                for n_idx in range(5):
                    recipient = member_users[n_idx % len(member_users)]
                    sender = pm_users[n_idx % len(pm_users)]
                    task = parent_tasks[n_idx % len(parent_tasks)]
                    
                    Notification.objects.create(
                        recipient=recipient,
                        sender=sender,
                        notification_type="task_assigned",
                        title=f"Task Assignment: {task.title}",
                        message=f"{sender.get_full_name()} assigned you a development task for {project.name}.",
                        is_read=False
                    )

                # Update progress once at the end
                project.update_progress()

        self.stdout.write(self.style.SUCCESS("\n✅ Database seeded successfully with 20 requirements, 12 parent tasks, 10 subtasks, and 22 approved test cases per project!\n"))
