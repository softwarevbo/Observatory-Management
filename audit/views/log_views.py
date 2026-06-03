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


@method_decorator(admin_required, name="dispatch")
class AuditLogPageView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        logs, users = AuditLog.objects.all().order_by(
            "-timestamp"
        ), InventoryUser.objects.all().order_by("username")
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

        if user_id and str(user_id).isdigit():
            logs = logs.filter(user_id=user_id)
        if year and str(year).isdigit():
            logs = logs.filter(timestamp__year=year)
        if month and str(month).isdigit():
            logs = logs.filter(timestamp__month=month)
        if date:
            logs = logs.filter(timestamp__date=date)
        if start_date and end_date:
            logs = logs.filter(timestamp__date__range=[start_date, end_date])
        elif start_date:
            logs = logs.filter(timestamp__date__gte=start_date)
        elif end_date:
            logs = logs.filter(timestamp__date__lte=end_date)
        if search:
            logs = logs.filter(
                Q(action__icontains=search)
                | Q(model_name__icontains=search)
                | Q(object_id__icontains=search)
                | Q(changes__icontains=search)
                | Q(user__username__icontains=search)
            )
        if action_filter:
            logs = logs.filter(action__icontains=action_filter)
        if model_filter:
            logs = logs.filter(model_name__icontains=model_filter)
        logs = filter_by_branch(logs, request.user)
        if branch_id and branch_id.isdigit():
            logs = logs.filter(branch_id=branch_id)

        if export == "excel":
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
            if not df.empty and "Timestamp" in df.columns:
                df["Timestamp"] = df["Timestamp"].apply(
                    lambda x: (
                        x.isoformat(sep=" ", timespec="minutes")
                        if pd.notnull(x)
                        else ""
                    )
                )
            response = HttpResponse(
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            response["Content-Disposition"] = "attachment; filename=audit_logs.xlsx"
            with pd.ExcelWriter(response, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Audit Logs")
            return response

        if export == "pdf":
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, "Audit Logs", ln=True, align="C")
            pdf.ln(5)
            pdf.set_font("Arial", "B", 10)
            headers, col_widths = [
                "User",
                "Action",
                "Model",
                "Object ID",
                "Timestamp",
                "Changes",
            ], [30, 20, 25, 20, 40, 55]
            for i, h in enumerate(headers):
                pdf.cell(col_widths[i], 8, h, border=1)
            pdf.ln()
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
            response = HttpResponse(
                pdf.output(dest="S").encode("latin1"), content_type="application/pdf"
            )
            response["Content-Disposition"] = "attachment; filename=audit_logs.pdf"
            return response

        paginator = Paginator(logs, 50)
        page_obj = paginator.get_page(request.GET.get("page"))
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
                "preserved_query": urlencode(query_params, doseq=True),
            },
        )
