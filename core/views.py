import os
from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import redirect, render

"""
This module contains global core views (such as custom error pages handler).
"""

def startfolder_view(request):
    """
    Renders the landing page from startfolder/index.html when accessing root URL.
    """
    file_path = settings.BASE_DIR / "startfolder" / "index.html"
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return HttpResponse(content, content_type="text/html")
    return render(request, "404.html", status=404)

def serve_startfolder_asset(request, filename):
    """
    Serves static assets (images, logos) located in the startfolder.
    """
    file_path = settings.BASE_DIR / "startfolder" / filename
    if file_path.exists():
        return FileResponse(open(file_path, "rb"))
    raise Http404("Asset not found")

def home_redirect_view(request):
    """
    Redirects authenticated users to their corresponding default home portal based on authorization.
    """
    if not request.user.is_authenticated:
        return redirect("accounts:login")

    if request.session.get("inv_user_id"):
        return redirect("/inventory/dashboard/")

    if not request.user.is_superuser and not getattr(request.user, "is_admin", False) and not getattr(request.user, "can_access_pm", False) and getattr(request.user, "can_access_telescope", False):
        return redirect("telescope:dashboard")

    return redirect("tasks:dashboard")

def custom_page_not_found_view(request, exception=None):
    """
    Renders the custom 404 Error Page template.
    Returns status code 404 to the browser.
    """
    return render(request, "404.html", status=404)
