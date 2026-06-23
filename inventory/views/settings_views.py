import io
import os
import tempfile
from django.shortcuts import render, redirect
from django.views import View
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.management import call_command
from django.http import HttpResponse
from django.utils.decorators import method_decorator

from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from ..models import InventoryUser, SystemSettings, Branch
from inventory.decorators import branch_admin_required, super_admin_required

"""
This module processes system configurations settings, database backup triggers, and permission matrices.
"""

PERMISSION_FIELDS = [
    ("can_access_adjustments_page", "Adjustments: Page Access"),
    ("can_manage_adjustments", "Adjustments: Manage Actions"),
    ("can_access_serials_page", "Serials: Page Access"),
    ("can_manage_serials", "Serials: Manage Actions"),
    ("can_access_limits_page", "Limits: Page Access"),
    ("can_manage_limits", "Limits: Manage Actions"),
    ("can_access_alerts_page", "Alerts: Page Access"),
    ("can_manage_alerts", "Alerts: Manage Actions"),
    ("can_access_rentals_page", "Rentals: Page Access"),
    ("can_manage_rentals", "Rentals: Manage Actions"),
    ("can_access_shortage_page", "Shortage: Page Access"),
    ("can_manage_shortage_exports", "Shortage: Export Actions"),
]


@method_decorator(super_admin_required, name="dispatch")
class DatabaseBackupView(LoginRequiredMixin, View):
    """
    View class handling JSON imports / exports of the inventory databases
    and processing permission checkboxes updates.
    """
    def get(self, request):
        is_global = getattr(request.user, "is_super_admin", False)
        inventory_users = InventoryUser.objects.all().order_by("role", "username")
        
        if is_global:
            settings = SystemSettings.get_settings()
        elif getattr(request.user, "branch", None):
            settings = SystemSettings.get_settings(branch=request.user.branch)
        else:
            settings = SystemSettings.get_settings()

        return render(
            request,
            "inventory/settings.html",
            {
                "inventory_users": inventory_users,
                "permission_fields": PERMISSION_FIELDS,
                "is_global": is_global,
                "settings": settings,
                "branches": Branch.objects.all() if is_global else [],
            },
        )

    def post(self, request):
        action = request.POST.get("action")
        if action == "update_controls":
            # Updates user permissions based on checkbox inputs
            inventory_users = InventoryUser.objects.all()
            field_names = [field for field, _ in PERMISSION_FIELDS]
            for inventory_user in inventory_users:
                for field_name in field_names:
                    checkbox_name = f"{field_name}_{inventory_user.id}"
                    setattr(
                        inventory_user,
                        field_name,
                        request.POST.get(checkbox_name) == "on",
                    )
                inventory_user.save(update_fields=field_names)
            messages.success(
                request, "Inventory user control restrictions updated successfully."
            )
            return redirect("inventory_settings")

        if action == "export":
            # Dumps database parameters to a JSON response stream
            out = io.StringIO()
            call_command(
                "dumpdata",
                "inventory",
                "accounts",
                "products",
                "stock",
                "procurement",
                "audit",
                "finance",
                "events",
                "tasks",
                "files",
                "notes",
                "bugs",
                "chat",
                "telescope",
                "resource_hub",
                stdout=out,
                indent=2,
            )
            response = HttpResponse(out.getvalue(), content_type="application/json")
            response["Content-Disposition"] = (
                'attachment; filename="inventory_backup.json"'
            )
            return response

        elif action == "import":
            # Restores database state using django loaddata command
            backup_file = request.FILES.get("backup_file")
            if not backup_file:
                messages.error(request, "Please provide a valid backup json file.")
                return redirect("inventory_settings")
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
                    for chunk in backup_file.chunks():
                        tmp.write(chunk)
                    tmp_path = tmp.name
                call_command("loaddata", tmp_path)
                os.unlink(tmp_path)
                messages.success(request, "Database successfully restored from backup!")
            except Exception as e:
                messages.error(request, f"Failed to restore backup: {str(e)}")
            return redirect("inventory_settings")
        return redirect("inventory_settings")


@method_decorator(branch_admin_required, name="dispatch")
class SystemSettingsView(View):
    """
    View class handling system settings configuration changes (site name, logo, notifications).
    Handles settings at either the global level (Super Admin) or branch level (Branch Admin).
    """
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        context = {"is_global": False, "permission_fields": PERMISSION_FIELDS}
        if getattr(request.user, "is_super_admin", False):
            global_settings = SystemSettings.get_settings()
            branches = Branch.objects.all()
            inventory_users = InventoryUser.objects.all().order_by("role", "username")
            context.update(
                {
                    "settings": global_settings,
                    "branches": branches,
                    "inventory_users": inventory_users,
                    "is_global": True,
                }
            )
        elif getattr(request.user, "branch", None):
            branch_settings = SystemSettings.get_settings(branch=request.user.branch)
            context.update({"settings": branch_settings})
        else:
            messages.error(request, "You do not have a branch assigned.")
            return redirect("dashboard")
        return render(request, "inventory/settings.html", context)

    def post(self, request):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        branch_id = request.POST.get("branch_id")
        if branch_id and getattr(request.user, "is_super_admin", False):
            branch = Branch.objects.get(id=branch_id)
            settings = SystemSettings.get_settings(branch=branch)
        elif not getattr(request.user, "is_super_admin", False) and getattr(request.user, "branch", None):
            settings = SystemSettings.get_settings(branch=request.user.branch)
        else:
            settings = SystemSettings.get_settings()
        settings.site_name = request.POST.get("site_name", settings.site_name)
        settings.contact_email = request.POST.get(
            "contact_email", settings.contact_email
        )
        settings.enable_notifications = request.POST.get("enable_notifications") == "on"
        settings.enable_low_stock_alerts = (
            request.POST.get("enable_low_stock_alerts") == "on"
        )
        if request.FILES.get("site_logo"):
            settings.site_logo = request.FILES.get("site_logo")
        settings.save()
        messages.success(request, "Settings updated successfully!")
        return redirect("system-settings")
