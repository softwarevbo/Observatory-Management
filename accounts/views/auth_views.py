from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from ..forms import LoginForm, UserSelfPasswordChangeForm


@never_cache
def login_view(request):
    if request.user.is_authenticated:
        return redirect(reverse("tasks:dashboard"))
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
            if not user.is_superuser and not user.can_access_pm:
                messages.error(
                    request,
                    "Access Denied: You do not have permission to access the Project Management System.",
                )
                return render(request, "accounts/login.html", {"form": form})
            login(request, user)
            if "inv_user_id" in request.session:
                del request.session["inv_user_id"]
            messages.success(request, f"Welcome back, {user.display_name}!")
            next_url = request.POST.get("next") or request.GET.get("next", "")
            if next_url:
                return redirect(next_url)
            return redirect(reverse("tasks:dashboard"))
        messages.error(request, "Invalid username or password.")
    return render(request, "accounts/login.html", {"form": form})


@never_cache
def inventory_login(request):
    if request.method == "POST":
        username, password = request.POST.get("username"), request.POST.get("password")
        try:
            from inventory.models import InventoryUser

            user = InventoryUser.objects.get(username=username)
            if user.check_password(password) and user.is_active:
                logout(request)
                request.session["inv_user_id"] = user.id
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect("/inventory/dashboard/")
            messages.error(
                request, "Invalid inventory credentials or inactive account."
            )
        except:
            messages.error(request, "Invalid inventory credentials.")
        return render(request, "accounts/login.html", {"form": LoginForm(request)})
    return redirect("accounts:login")


def logout_view(request):
    name = getattr(request.user, "display_name", "")
    if "inv_user_id" in request.session:
        try:
            from inventory.models import InventoryUser

            inv_user = InventoryUser.objects.get(id=request.session["inv_user_id"])
            if not name:
                name = inv_user.username
        except:
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


@never_cache
def telescope_login(request):
    if request.method == "POST":
        from django.contrib.auth import authenticate
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if not user.is_active:
                messages.error(request, "Your account has been deactivated. Contact the administrator.")
                return redirect("accounts:login")
            if not user.is_superuser and not user.can_access_telescope:
                messages.error(request, "Access Denied: You do not have permission to access the Telescope Control System.")
                return redirect("accounts:login")
            login(request, user)
            messages.success(request, f"Welcome to the Telescope Control System, {user.display_name}!")
            return redirect("/telescope/")
        messages.error(request, "Invalid username or password.")
    return redirect("accounts:login")
