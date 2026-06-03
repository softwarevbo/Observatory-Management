from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from ..models import AuditLog
from django.core.paginator import Paginator

@login_required
def audit_log_list(request):
    if not request.user.is_admin:
        return render(request, "403.html", status=403)
        
    logs = AuditLog.objects.all().select_related('user')
    
    # Filtering
    module_filter = request.GET.get('module')
    action_filter = request.GET.get('action')
    user_filter = request.GET.get('user')
    
    if module_filter:
        logs = logs.filter(module=module_filter)
    if action_filter:
        logs = logs.filter(action_type=action_filter)
    if user_filter:
        logs = logs.filter(user__username=user_filter)
        
    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        "page_obj": page_obj,
        "module_choices": AuditLog.MODULE_CHOICES,
        "action_choices": AuditLog.ACTION_CHOICES,
        "module_filter": module_filter,
        "action_filter": action_filter,
        "user_filter": user_filter,
    }
    return render(request, "audit/audit_log_list.html", context)
