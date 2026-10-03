from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache

from ..forms import LoginForm, UserSelfPasswordChangeForm
from ..rbac import (
    can_login_to_module,
    get_canonical_role,
    get_default_redirect_for_role,
    has_permission,
    PERMISSION_INVENTORY_ACCESS,
    PERMISSION_PROJECT_ACCESS,
    PERMISSION_TELESCOPE_ACCESS,
)

"""
Authentication views enforcing module-based role isolation.
Entry points:
1. Project Management Login: ROOT, PM_ADMIN, PM_MEMBER.
2. Telescope Management Login: ROOT, TM_ADMIN, TM_MEMBER.
3. Inventory Management Login: ROOT, IM_ADMIN, IM_MEMBER.
"""


@never_cache
def login_view(request):
    """
    Handles Project Management Login.
    Allowed roles: ROOT, PM_ADMIN, PM_MEMBER.
    Denied roles: TM_ADMIN, TM_MEMBER, IM_ADMIN, IM_MEMBER.
    """
    if request.user.is_authenticated:
        redirect_url = get_default_redirect_for_role(request.user)
        return redirect(redirect_url)

    form = LoginForm(request, data=request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            user = form.get_user()

            if not user.is_active:
                messages.error(
                    request,
                    "Your account has been deactivated. Contact the administrator.",
                )
                return render(request, "accounts/login.html", {"form": form})

            # Check Project Management Login Restriction
            if not can_login_to_module(user, "project"):
                messages.error(
                    request,
                    "Access Denied: Your role does not have permission to access Project Management.",
                )
                return render(request, "accounts/login.html", {"form": form})

            login(request, user)

            if "inv_user_id" in request.session:
                del request.session["inv_user_id"]

            messages.success(request, f"Welcome back, {user.display_name}!")

            next_url = request.POST.get("next") or request.GET.get("next", "")
            if next_url and next_url.startswith("/"):
                return redirect(next_url)
            return redirect(reverse("tasks:dashboard"))

        messages.error(request, "Invalid username or password.")

    return render(request, "accounts/login.html", {"form": form})


@never_cache
def telescope_login(request):
    """
    Handles Telescope Management Login.
    Allowed roles: ROOT, TM_ADMIN, TM_MEMBER.
    Denied roles: PM_ADMIN, PM_MEMBER, IM_ADMIN, IM_MEMBER.
    Authenticates standard User model AND custom TelescopeUser model.
    """
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()

        # 1. First attempt authenticating via standard Django User model
        user = authenticate(request, username=username, password=password)

        if user is not None:
            if not user.is_active:
                messages.error(
                    request,
                    "Your account has been deactivated. Contact the administrator.",
                )
                return redirect("accounts:login")

            # Check Telescope Management Login Restriction
            if not can_login_to_module(user, "telescope"):
                messages.error(
                    request,
                    "Access Denied: Your role does not have permission to access Telescope Management.",
                )
                return redirect("accounts:login")

            login(request, user)

            if "inv_user_id" in request.session:
                del request.session["inv_user_id"]
            if "tele_user_id" in request.session:
                del request.session["tele_user_id"]

            messages.success(
                request, f"Welcome to the Telescope Control System, {user.display_name}!"
            )
            next_url = request.POST.get("next") or request.GET.get("next", "")
            if next_url and next_url.startswith("/"):
                return redirect(next_url)
            return redirect("/telescopecontrol/")

        # 2. Next attempt authenticating via custom TelescopeUser model
        try:
            from telescope.models import TelescopeUser

            tele_user = TelescopeUser.objects.get(username=username)

            if tele_user.check_password(password) and tele_user.is_active:
                logout(request)
                request.session["tele_user_id"] = tele_user.id
                messages.success(
                    request, f"Welcome to the Telescope Control System, {tele_user.username}!"
                )
                next_url = request.POST.get("next") or request.GET.get("next", "")
                if next_url and next_url.startswith("/"):
                    return redirect(next_url)
                return redirect("/telescopecontrol/")

            messages.error(
                request, "Invalid telescope credentials or inactive account."
            )
        except Exception:
            messages.error(request, "Invalid username or password for Telescope Management.")

    return redirect("accounts:login")


@never_cache
def inventory_login(request):
    """
    Handles Inventory Management Login.
    Allowed roles: ROOT, IM_ADMIN, IM_MEMBER.
    Denied roles: PM_ADMIN, PM_MEMBER, TM_ADMIN, TM_MEMBER.
    Authenticates standard User model AND custom InventoryUser model.
    """
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()

        # 1. First attempt authenticating via standard Django User model
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if not user.is_active:
                messages.error(
                    request,
                    "Your account has been deactivated. Contact the administrator.",
                )
                return render(request, "accounts/login.html", {"form": LoginForm(request)})

            if not can_login_to_module(user, "inventory"):
                messages.error(
                    request,
                    "Access Denied: Your role does not have permission to access Inventory Management.",
                )
                return render(request, "accounts/login.html", {"form": LoginForm(request)})

            login(request, user)
            if "inv_user_id" in request.session:
                del request.session["inv_user_id"]

            messages.success(request, f"Welcome back, {user.display_name}!")
            next_url = request.POST.get("next") or request.GET.get("next", "")
            if next_url and next_url.startswith("/"):
                return redirect(next_url)
            return redirect("/inventorymanagement/dashboard/")

        # 2. Next attempt authenticating via custom InventoryUser model
        try:
            from inventory.models import InventoryUser

            inv_user = InventoryUser.objects.get(username=username)

            if inv_user.check_password(password) and inv_user.is_active:
                if not can_login_to_module(inv_user, "inventory"):
                    messages.error(
                        request,
                        "Access Denied: Your role does not have permission to access Inventory Management.",
                    )
                    return render(
                        request, "accounts/login.html", {"form": LoginForm(request)}
                    )

                logout(request)
                request.session["inv_user_id"] = inv_user.id
                messages.success(request, f"Welcome back, {inv_user.username}!")
                return redirect("/inventorymanagement/dashboard/")

            messages.error(
                request, "Invalid inventory credentials or inactive account."
            )
        except Exception:
            messages.error(request, "Invalid inventory credentials.")

        return render(request, "accounts/login.html", {"form": LoginForm(request)})



    return redirect("accounts:login")


def logout_view(request):
    """
    Logs out the user and flushes their active session entirely.
    """
    name = getattr(request.user, "display_name", "")

    if "inv_user_id" in request.session:
        try:
            from inventory.models import InventoryUser

            inv_user = InventoryUser.objects.get(id=request.session["inv_user_id"])
            if not name:
                name = inv_user.username
        except Exception:
            pass

    request.session.flush()
    logout(request)

    messages.info(
        request,
        (
            f"Goodbye, {name}! You have been logged out."
            if name
            else "You have been logged out."
        ),
    )
    return redirect("accounts:login")


def change_password(request):
    """
    Allows a logged-in user to modify their own password.
    """
    form = UserSelfPasswordChangeForm(user=request.user, data=request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            request.user.set_password(form.cleaned_data["new_password1"])
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, "✅ Your password has been changed successfully.")
            return redirect("accounts:profile")

        messages.error(request, "Please fix the errors below.")
    return render(request, "accounts/change_password.html", {"form": form})
