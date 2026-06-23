from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from ..forms import LoginForm, UserSelfPasswordChangeForm

"""
This module handles authentication views for the system.
It supports:
1. Standard Project Management (PM) user login with active checks.
2. Separate Inventory portal credentials authentication utilizing the `InventoryUser` model.
3. Telescope Control portal authentications.
4. Global session logouts and self password updates.
"""

@never_cache
def login_view(request):
    """
    Handles standard user login.
    Using `@never_cache` ensures that the login page and response are never cached by the browser,
    preventing security leaks when users log out and press back.
    """
    # If the user is already logged in, redirect them immediately to their designated portal
    if request.user.is_authenticated:
        if not request.user.is_superuser and not getattr(request.user, "is_admin", False) and not getattr(request.user, "can_access_pm", False) and getattr(request.user, "can_access_telescope", False):
            return redirect(reverse("telescope:dashboard"))
        return redirect(reverse("tasks:dashboard"))
    
    # Initialize the custom login form with POST data if present, otherwise None
    form = LoginForm(request, data=request.POST or None)
    
    if request.method == "POST":
        if form.is_valid():
            # Retrieve the authenticated user instance from the form
            user = form.get_user()
            
            # Assert that the user account status is Active
            if not user.is_active:
                messages.error(
                    request,
                    "Your account has been deactivated. Contact the administrator.",
                )
                return render(request, "accounts/login.html", {"form": form})
            
            # Assert that the user has general Project Management access rights
            if not user.is_admin and not user.can_access_pm:
                messages.error(
                    request,
                    "Access Denied: You do not have permission to access the Project Management System.",
                )
                return render(request, "accounts/login.html", {"form": form})
            
            # Log the user into the current session. Django updates session tokens behind the scenes.
            login(request, user)
            
            # If there was a leftovers inventory session ID in the browser, clean it up
            if "inv_user_id" in request.session:
                del request.session["inv_user_id"]
                
            messages.success(request, f"Welcome back, {user.display_name}!")
            
            # Handle post-login redirection if 'next' parameter is provided (e.g. from redirecting deep-link URLs)
            next_url = request.POST.get("next") or request.GET.get("next", "")
            if next_url:
                return redirect(next_url)
            return redirect(reverse("tasks:dashboard"))
        
        # Display an error message if form validation fails
        messages.error(request, "Invalid username or password.")
        
    return render(request, "accounts/login.html", {"form": form})


@never_cache
def inventory_login(request):
    """
    Handles separate authentication for Inventory-only users.
    Inventory users are not stored in standard User table; they are verified 
    against the custom `InventoryUser` model. We set `inv_user_id` in session 
    to track authorization.
    """
    if request.method == "POST":
        username, password = request.POST.get("username"), request.POST.get("password")
        try:
            from inventory.models import InventoryUser

            # Fetch the matching inventory user
            user = InventoryUser.objects.get(username=username)
            
            # Validate password and active status
            if user.check_password(password) and user.is_active:
                # Log out any currently logged-in standard PM user to prevent mixed authorization states
                logout(request)
                
                # Store the custom inventory user ID in session storage
                request.session["inv_user_id"] = user.id
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect("/inventory/dashboard/")
            
            messages.error(
                request, "Invalid inventory credentials or inactive account."
            )
        except Exception:
            messages.error(request, "Invalid inventory credentials.")
            
        return render(request, "accounts/login.html", {"form": LoginForm(request)})
    
    # Redirect GET requests to the standard login page
    return redirect("accounts:login")


def logout_view(request):
    """
    Logs out the user and flushes their active session entirely.
    """
    name = getattr(request.user, "display_name", "")
    
    # Check if this logout originates from an inventory session
    if "inv_user_id" in request.session:
        try:
            from inventory.models import InventoryUser
            inv_user = InventoryUser.objects.get(id=request.session["inv_user_id"])
            if not name:
                name = inv_user.username
        except Exception:
            pass
            
    # Flush destroys all session cookies and data inside backend session store
    request.session.flush()
    
    # Triggers Django logout to remove user reference from session context
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
    Requires inputting current password for security verification.
    """
    form = UserSelfPasswordChangeForm(user=request.user, data=request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            # Update password and save changes
            request.user.set_password(form.cleaned_data["new_password1"])
            request.user.save()
            
            # IMPORTANT: Updating password invalidates the session hash which causes log out.
            # update_session_auth_hash keeps the user logged in after their password is changed.
            update_session_auth_hash(request, request.user)
            
            messages.success(request, "✅ Your password has been changed successfully.")
            return redirect("accounts:profile")
        
        messages.error(request, "Please fix the errors below.")
    return render(request, "accounts/change_password.html", {"form": form})


@never_cache
def telescope_login(request):
    """
    Handles user login specifically for the Telescope Control portal.
    Authenticates standard User, but verifies they have explicit telescope access rights.
    """
    if request.method == "POST":
        from django.contrib.auth import authenticate
        
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        
        # Authenticate checks credentials against database records
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if not user.is_active:
                messages.error(request, "Your account has been deactivated. Contact the administrator.")
                return redirect("accounts:login")
            
            # Verify authorization access rights to the telescope module
            if not user.is_admin and not user.can_access_telescope:
                messages.error(request, "Access Denied: You do not have permission to access the Telescope Control System.")
                return redirect("accounts:login")
            
            login(request, user)
            messages.success(request, f"Welcome to the Telescope Control System, {user.display_name}!")
            return redirect("/telescope/")
        
        messages.error(request, "Invalid username or password.")
        
    return redirect("accounts:login")
