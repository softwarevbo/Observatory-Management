from django.shortcuts import render

"""
This module contains global core views (such as custom error pages handler).
"""

def custom_page_not_found_view(request, exception=None):
    """
    Renders the custom 404 Error Page template.
    Returns status code 404 to the browser.
    """
    return render(request, "404.html", status=404)
