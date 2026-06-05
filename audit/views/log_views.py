from urllib.parse import urlencode
import pandas as pd
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from fpdf import FPDF

from inventory.models import InventoryUser, Branch
from inventory.utils import filter_by_branch
from tasks.decorators import admin_required
from ..models import AuditLog

"""
This module contains the HTTP View logic for managing audit logs.
It features:
1. Class-Based Views (CBVs) using Django's View model.
2. Custom administrative access control checking using method decorators.
3. Complex queryset search filters matching various parameters (user, year, month, date, ranges).
4. Direct Excel sheet exports compiled using pandas.
5. Dynamic PDF document downloads compiled using the FPDF package.
6. Clean page pagination preserving active filter query strings.
"""

@method_decorator(admin_required, name="dispatch")
class AuditLogPageView(View):
    """
    Class-based view for rendering and exporting audit logs.
    
    Using `@method_decorator(admin_required, name="dispatch")` applies the admin-only check 
    to the dispatch method, securing all HTTP actions (GET, POST, etc.) inside the view.
    """
    
    def get(self, request):
        """
        Processes GET requests for listing, filtering, and exporting log datasets.
        """
        # Extra safety check to verify user login state
        if not request.user.is_authenticated:
            return redirect("accounts:login")
            
        # Initialize initial querysets
        logs = AuditLog.objects.all().order_by("-timestamp")
        users = InventoryUser.objects.all().order_by("username")
        
        # Extract query parameters from request.GET dictionary
        (
            user_id,
            year,
            month,
            date,
            search,
            export,
            start_date,
            end_date,
            action_filter,
            model_filter,
            branch_id,
        ) = (
            request.GET.get("user"),
            request.GET.get("year"),
            request.GET.get("month"),
            request.GET.get("date"),
            request.GET.get("search"),
            request.GET.get("export"),
            request.GET.get("start_date"),
            request.GET.get("end_date"),
            request.GET.get("action", "").strip(),
            request.GET.get("model", "").strip(),
            request.GET.get("branch_id"),
        )

        # ─── Query Filtering Hooks ───
        # Filter by specific user
        if user_id and str(user_id).isdigit():
            logs = logs.filter(user_id=user_id)
            
        # Filter by specific calendar year
        if year and str(year).isdigit():
            logs = logs.filter(timestamp__year=year)
            
        # Filter by specific calendar month (1-12)
        if month and str(month).isdigit():
            logs = logs.filter(timestamp__month=month)
            
        # Filter by specific date
        if date:
            logs = logs.filter(timestamp__date=date)
            
        # Filter by date ranges
        if start_date and end_date:
            logs = logs.filter(timestamp__date__range=[start_date, end_date])
        elif start_date:
            logs = logs.filter(timestamp__date__gte=start_date)
        elif end_date:
            logs = logs.filter(timestamp__date__lte=end_date)
            
        # Filter by text search matching action descriptions, models, primary keys, or usernames
        if search:
            logs = logs.filter(
                Q(action__icontains=search)
                | Q(model_name__icontains=search)
                | Q(object_id__icontains=search)
                | Q(changes__icontains=search)
                | Q(user__username__icontains=search)
            )
            
        # Filter by action type (e.g. Create, Update)
        if action_filter:
            logs = logs.filter(action__icontains=action_filter)
            
        # Filter by database model type name
        if model_filter:
            logs = logs.filter(model_name__icontains=model_filter)
            
        # Filters database queries by user's assigned warehouse branch permissions (data isolation)
        logs = filter_by_branch(logs, request.user)
        
        # Filter by specific warehouse branch
        if branch_id and branch_id.isdigit():
            logs = logs.filter(branch_id=branch_id)

        # ─── EXPORT OPTION: EXCEL SHEET GENERATION ───
        if export == "excel":
            # Extract database values dictionary directly
            df = pd.DataFrame(
                list(
                    logs.values(
                        "user__username",
                        "action",
                        "model_name",
                        "object_id",
                        "timestamp",
                        "changes",
                    )
                )
            )
            # Rename data frame columns for clean presentation headings
            df.rename(
                columns={
                    "user__username": "User",
                    "action": "Action",
                    "model_name": "Model",
                    "object_id": "Object ID",
                    "timestamp": "Timestamp",
                    "changes": "Changes",
                },
                inplace=True,
            )
            
            # Format timestamp strings to ISO standards
            if not df.empty and "Timestamp" in df.columns:
                df["Timestamp"] = df["Timestamp"].apply(
                    lambda x: (
                        x.isoformat(sep=" ", timespec="minutes")
                        if pd.notnull(x)
                        else ""
                    )
                )
                
            # Initialize HTTP response with appropriate spreadsheet MIME content-type
            response = HttpResponse(
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            response["Content-Disposition"] = "attachment; filename=audit_logs.xlsx"
            
            # Use Pandas ExcelWriter with openpyxl engine to write spreadsheet directly to response stream
            with pd.ExcelWriter(response, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Audit Logs")
            return response

        # ─── EXPORT OPTION: PDF DOCUMENT GENERATION ───
        if export == "pdf":
            pdf = FPDF()
            pdf.add_page()
            
            # Page Title
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, "Audit Logs", ln=True, align="C")
            pdf.ln(5)
            
            # Set Table Headings
            pdf.set_font("Arial", "B", 10)
            headers, col_widths = [
                "User",
                "Action",
                "Model",
                "Object ID",
                "Timestamp",
                "Changes",
            ], [30, 20, 25, 20, 40, 55]
            
            # Render table headings cells
            for i, h in enumerate(headers):
                pdf.cell(col_widths[i], 8, h, border=1)
            pdf.ln()
            
            # Render logs rows (limiting to top 200 records to prevent PDF memory overflows)
            pdf.set_font("Arial", "", 9)
            for log in logs[:200]:
                row = [
                    str(log.user) if log.user else "System",
                    log.action,
                    log.model_name,
                    str(log.object_id),
                    log.timestamp.strftime("%Y-%m-%d %H:%M"),
                    (
                        (log.changes[:40] + "...")
                        if log.changes and len(log.changes) > 40
                        else (log.changes or "-")
                    ),
                ]
                for i, cell in enumerate(row):
                    pdf.cell(col_widths[i], 8, cell, border=1)
                pdf.ln()
                
            # Stream PDF file response using latin1 string encoding
            response = HttpResponse(
                pdf.output(dest="S").encode("latin1"), content_type="application/pdf"
            )
            response["Content-Disposition"] = "attachment; filename=audit_logs.pdf"
            return response

        # ─── DEFAULT PATH: RENDER HTML LOG LIST ───
        # Paginate results (50 logs per page)
        paginator = Paginator(logs, 50)
        page_obj = paginator.get_page(request.GET.get("page"))
        
        # Copy request parameter map to preserve filters during pagination links
        query_params = request.GET.copy()
        query_params.pop("page", None)
        query_params.pop("export", None)
        
        return render(
            request,
            "audit/logs.html",
            {
                "logs": page_obj.object_list,
                "page_obj": page_obj,
                "users": users,
                "branches": Branch.objects.all() if request.user.is_super_admin else [],
                "years": AuditLog.objects.dates("timestamp", "year", order="DESC"),
                "months": range(1, 13),
                "selected_user": user_id,
                "selected_branch": branch_id,
                "selected_year": year,
                "selected_month": month,
                "selected_date": date,
                "search": search,
                "start_date": start_date,
                "end_date": end_date,
                "action_filter": action_filter,
                "model_filter": model_filter,
                # Preserved Query represents the active filters serialized to pass into next/prev links
                "preserved_query": urlencode(query_params, doseq=True),
            },
        )
