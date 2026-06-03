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

from ..models import InventoryUser, SystemSettings, Branch
from tasks.decorators import admin_required

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


@method_decorator(admin_required, name="dispatch")
class DatabaseBackupView(LoginRequiredMixin, View):
    def get(self, request):
        inventory_users = InventoryUser.objects.all().order_by("role", "username")
        return render(
            request,
            "inventory/settings.html",
            {
                "inventory_users": inventory_users,
                "permission_fields": PERMISSION_FIELDS,
            },
        )

    def post(self, request):
        action = request.POST.get("action")
        if action == "update_controls":
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
            out = io.StringIO()
            call_command(
                "dumpdata",
                "products",
                "stock",
                "procurement",
                "inventory",
                stdout=out,
                indent=2,
            )
            response = HttpResponse(out.getvalue(), content_type="application/json")
            response["Content-Disposition"] = (
                'attachment; filename="inventory_backup.json"'
            )
            return response

        elif action == "import":
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


class SystemSettingsView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        context = {"is_global": False, "permission_fields": PERMISSION_FIELDS}
        if request.user.is_super_admin:
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
        elif request.user.branch:
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
        if branch_id and request.user.is_super_admin:
            branch = Branch.objects.get(id=branch_id)
            settings = SystemSettings.get_settings(branch=branch)
        elif not request.user.is_super_admin and request.user.branch:
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
