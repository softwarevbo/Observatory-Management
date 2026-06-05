from io import BytesIO
import pandas as pd
from django.db.models import Count, Sum
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views import View

from audit.models import AuditLog
from inventory.models import Alert, InventoryAdjustment, Rental, BranchStock
from procurement.models import ProcurementRequest
from products.models import Category
from stock.models import StockEntry
from inventory.utils import (
    filter_by_branch,
    get_isolated_products,
    has_global_inventory_access,
)


class StatisticsReportView(View):
    """
    Renders the unified analytics dashboard with graphs, metrics, and transaction history.
    """
    def get(self, request):
        # Validate that the request session user is authenticated
        if not request.user.is_authenticated:
            return redirect("accounts:login")
            
        # Determine global access permission and fetch the user's home branch if any
        is_global, user_branch = has_global_inventory_access(request.user), getattr(
            request.user, "branch", None
        )
        
        # Scrutinize branch boundaries: filter all querysets based on branch privileges
        (
            products_qs,
            stock_entries_qs,
            rentals_qs,
            adjustments_qs,
            alerts_qs,
            procurement_qs,
        ) = (
            get_isolated_products(request.user),
            filter_by_branch(StockEntry.objects.all(), request.user),
            filter_by_branch(Rental.objects.all(), request.user),
            filter_by_branch(InventoryAdjustment.objects.all(), request.user),
            filter_by_branch(Alert.objects.all(), request.user),
            filter_by_branch(ProcurementRequest.objects.all(), request.user),
        )
        
        # Calculate overall stock quantities scoped by branch boundaries
        current_stock = (
            BranchStock.objects.aggregate(total=Sum("current_quantity"))["total"]
            if is_global
            else BranchStock.objects.filter(branch=user_branch).aggregate(
                total=Sum("current_quantity")
            )["total"]
        ) or 0

        # Query categories annotated with the number of associated products
        category_breakdown = list(
            Category.objects.annotate(product_count=Count("products"))
            .values("name", "product_count")
            .order_by("-product_count")
            if is_global
            else Category.objects.filter(products__branch_stocks__branch=user_branch)
            .annotate(product_count=Count("products", distinct=True))
            .values("name", "product_count")
            .order_by("-product_count")
        )

        # Generate a chronological sequence of the past 12 months for timeseries reporting
        now = timezone.now()
        months = sorted(
            set(
                [
                    (now.replace(day=1) - timezone.timedelta(days=30 * i)).replace(
                        day=1
                    )
                    for i in range(12)
                ]
            )
        )
        # Format month names as e.g. "Jun 2026"
        month_labels = [m.strftime("%b %Y") for m in months]
        
        # Aggregate Stock-In volumes grouped by month
        stock_in_by_month = [
            stock_entries_qs.filter(
                timestamp__year=m.year, timestamp__month=m.month
            ).aggregate(total=Sum("quantity"))["total"]
            or 0
            for m in months
        ]
        # Aggregate Stock-Out volumes grouped by month
        stock_out_by_month = [
            stock_entries_qs.filter(
                timestamp__year=m.year, timestamp__month=m.month
            ).aggregate(total=Sum("quantity"))["total"]
            or 0
            for m in months
        ]

        # Calculate rental status splits for donut charts
        rental_status_breakdown = list(
            rentals_qs.values("status").annotate(count=Count("id"))
        )
        # Identify top 10 products by rental frequency
        rental_product_breakdown = list(
            rentals_qs.values("product__name")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )
        # Calculate alert types count breakdown
        alert_type_breakdown = list(
            alerts_qs.values("alert_type").annotate(count=Count("id"))
        )
        # Identify top 10 products triggering alerts
        alert_product_breakdown = list(
            alerts_qs.values("product__name")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )

        # Compile a unified transaction history feed by merging stock logs, adjustments, and procurement requests
        recent_transactions = sorted(
            [
                {
                    "timestamp": e.timestamp,
                    "type": f"stock_{e.entry_type}",
                    "ref": f"StockEntry#{e.id}",
                    "user": e.created_by.username if e.created_by else "System",
                    "description": f"{e.product.name} ({e.quantity})",
                }
                for e in stock_entries_qs.select_related(
                    "product", "created_by"
                ).order_by("-timestamp")[:40]
            ]
            + [
                {
                    "timestamp": a.timestamp,
                    "type": f"adjustment_{a.adjustment_type}",
                    "ref": f"Adjustment#{a.id}",
                    "user": a.created_by.username if a.created_by else "System",
                    "description": f"{a.product.name} ({a.quantity})",
                }
                for a in adjustments_qs.select_related(
                    "product", "created_by"
                ).order_by("-timestamp")[:40]
            ]
            + [
                {
                    "timestamp": r.created_at,
                    "type": "procurement_request",
                    "ref": f"Procurement#{r.id}",
                    "user": r.requester.username if r.requester else "System",
                    "description": f"{r.product_name} ({r.requested_quantity}) [{r.status}]",
                }
                for r in procurement_qs.select_related("requester").order_by(
                    "-created_at"
                )[:40]
            ],
            key=lambda x: x["timestamp"],
            reverse=True,
        )[:50] # Limit merged array to latest 50 logs

        # Render analytical context metrics onto HTML page
        return render(
            request,
            "reports/statistics.html",
            {
                "total_products": products_qs.count(),
                "total_stock_in": stock_entries_qs.filter(entry_type="in").aggregate(
                    total=Sum("quantity")
                )["total"]
                or 0,
                "total_stock_out": stock_entries_qs.filter(entry_type="out").aggregate(
                    total=Sum("quantity")
                )["total"]
                or 0,
                "current_stock": current_stock,
                "total_rentals": rentals_qs.count(),
                "active_rentals": rentals_qs.filter(status="active").count(),
                "overdue_rentals": rentals_qs.filter(status="overdue").count(),
                "total_adjustments": adjustments_qs.count(),
                "total_alerts": alerts_qs.count(),
                "active_alerts": alerts_qs.filter(status="active").count(),
                "category_breakdown": category_breakdown,
                "month_labels": month_labels,
                "stock_in_by_month": stock_in_by_month,
                "stock_out_by_month": stock_out_by_month,
                "rental_status_breakdown": rental_status_breakdown,
                "rental_product_breakdown": rental_product_breakdown,
                "alert_type_breakdown": alert_type_breakdown,
                "alert_product_breakdown": alert_product_breakdown,
                "category_names": [c["name"] for c in category_breakdown],
                "category_counts": [c["product_count"] for c in category_breakdown],
                "rental_status_labels": [
                    r["status"].title() for r in rental_status_breakdown
                ],
                "rental_status_counts": [r["count"] for r in rental_status_breakdown],
                "rental_product_names": [
                    r["product__name"] for r in rental_product_breakdown
                ],
                "rental_product_counts": [r["count"] for r in rental_product_breakdown],
                "alert_type_labels": [
                    a["alert_type"].replace("_", " ").title()
                    for a in alert_type_breakdown
                ],
                "alert_type_counts": [a["count"] for a in alert_type_breakdown],
                "alert_product_names": [
                    a["product__name"] for a in alert_product_breakdown
                ],
                "alert_product_counts": [a["count"] for a in alert_product_breakdown],
                "total_procurement_requests": procurement_qs.count(),
                "pending_procurement_requests": procurement_qs.filter(
                    status="pending"
                ).count(),
                "recent_transactions": recent_transactions,
            },
        )


def statistics_report_export(request, format):
    """
    Exports full analytical metrics database to Excel (multi-sheet), CSV, or PDF format.
    """
    # Validate that the request session user is authenticated
    if not request.user.is_authenticated:
        return redirect("accounts:login")
        
    # Query permissions and branch bounds
    is_global, user_branch = has_global_inventory_access(request.user), getattr(
        request.user, "branch", None
    )
    # Scopes data sets inside user branch boundaries
    (
        products_qs,
        stock_entries_qs,
        rentals_qs,
        adjustments_qs,
        alerts_qs,
        procurement_qs,
        audit_qs,
    ) = (
        get_isolated_products(request.user),
        filter_by_branch(StockEntry.objects.all(), request.user),
        filter_by_branch(Rental.objects.all(), request.user),
        filter_by_branch(InventoryAdjustment.objects.all(), request.user),
        filter_by_branch(Alert.objects.all(), request.user),
        filter_by_branch(ProcurementRequest.objects.all(), request.user),
        filter_by_branch(AuditLog.objects.all(), request.user),
    )
    # Calculate months range for export
    now = timezone.now()
    months = sorted(
        set(
            [
                (now.replace(day=1) - timezone.timedelta(days=30 * i)).replace(day=1)
                for i in range(12)
            ]
        )
    )
    month_labels = [m.strftime("%b %Y") for m in months]
    category_breakdown = list(
        Category.objects.annotate(product_count=Count("products"))
        .values("name", "product_count")
        .order_by("-product_count")
        if is_global
        else Category.objects.filter(products__branch_stocks__branch=user_branch)
        .annotate(product_count=Count("products", distinct=True))
        .values("name", "product_count")
        .order_by("-product_count")
    )

    # Compile timeseries stock-in quantities
    stock_in_by_month = [
        stock_entries_qs.filter(
            entry_type="in",
            timestamp__year=m.year,
            timestamp__month=m.month,
        ).aggregate(total=Sum("quantity"))["total"]
        or 0
        for m in months
    ]
    # Compile timeseries stock-out quantities
    stock_out_by_month = [
        stock_entries_qs.filter(
            entry_type="out",
            timestamp__year=m.year,
            timestamp__month=m.month,
        ).aggregate(total=Sum("quantity"))["total"]
        or 0
        for m in months
    ]

    # Create distinct Pandas DataFrames to map onto separate Excel sheets
    dfs = {
        "Summary": pd.DataFrame(
            [
                {
                    "Total Products": products_qs.count(),
                    "Total Stock In": stock_entries_qs.filter(
                        entry_type="in"
                    ).aggregate(total=Sum("quantity"))["total"]
                    or 0,
                    "Total Stock Out": stock_entries_qs.filter(
                        entry_type="out"
                    ).aggregate(total=Sum("quantity"))["total"]
                    or 0,
                    "Current Stock": (
                        BranchStock.objects.aggregate(total=Sum("current_quantity"))[
                            "total"
                        ]
                        if is_global
                        else BranchStock.objects.filter(branch=user_branch).aggregate(
                            total=Sum("current_quantity")
                        )["total"]
                    )
                    or 0,
                    "Total Rentals": rentals_qs.count(),
                    "Total Alerts": alerts_qs.count(),
                    "Total Procurement Requests": procurement_qs.count(),
                }
            ]
        ),
        "Products by Category": pd.DataFrame(category_breakdown),
        "Stock In-Out by Month": pd.DataFrame(
            {
                "Month": month_labels,
                "Stock In": stock_in_by_month,
                "Stock Out": stock_out_by_month,
            }
        ),
        "Rentals by Status": pd.DataFrame(
            list(rentals_qs.values("status").annotate(count=Count("id")))
        ),
        "Rentals by Product": pd.DataFrame(
            list(
                rentals_qs.values("product__name")
                .annotate(count=Count("id"))
                .order_by("-count")[:10]
            )
        ),
        "Alerts by Type": pd.DataFrame(
            list(alerts_qs.values("alert_type").annotate(count=Count("id")))
        ),
        "Alerts by Product": pd.DataFrame(
            list(
                alerts_qs.values("product__name")
                .annotate(count=Count("id"))
                .order_by("-count")[:10]
            )
        ),
        "Stock Entries": pd.DataFrame(
            list(
                stock_entries_qs.select_related("product", "created_by").values(
                    "id",
                    "entry_type",
                    "quantity",
                    "location_from",
                    "location_to",
                    "timestamp",
                    "description",
                    "product__name",
                    "created_by__username",
                )
            )
        ),
        "Inventory Adjustments": pd.DataFrame(
            list(
                adjustments_qs.select_related("product", "created_by").values(
                    "id",
                    "adjustment_type",
                    "quantity",
                    "reason",
                    "timestamp",
                    "product__name",
                    "created_by__username",
                )
            )
        ),
        "Rental Transactions": pd.DataFrame(
            list(
                rentals_qs.select_related("product", "created_by").values(
                    "id",
                    "product__name",
                    "quantity",
                    "rented_to",
                    "reason",
                    "rental_date",
                    "return_date",
                    "status",
                    "created_by__username",
                    "created_at",
                )
            )
        ),
        "Alert Transactions": pd.DataFrame(
            list(
                alerts_qs.select_related("product").values(
                    "id",
                    "product__name",
                    "alert_type",
                    "status",
                    "message",
                    "current_quantity",
                    "limit_quantity",
                    "created_at",
                )
            )
        ),
        "Procurement Requests": pd.DataFrame(
            list(
                procurement_qs.select_related("requester", "decided_by").values(
                    "id",
                    "product_name",
                    "requested_quantity",
                    "current_stock",
                    "status",
                    "requester__username",
                    "decision_reason",
                    "fulfilled_quantity",
                    "decided_by__username",
                    "decided_at",
                    "created_at",
                )
            )
        ),
        "Audit Logs": pd.DataFrame(
            list(
                audit_qs.select_related("user").values(
                    "id",
                    "user__username",
                    "action",
                    "model_name",
                    "object_id",
                    "timestamp",
                    "changes",
                )
            )
        ),
    }

    # Format 1: Excel download (.xlsx)
    if format == "excel":
        output = BytesIO()
        # Initialize Pandas ExcelWriter with xlsxwriter engine
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            for sheet, df in dfs.items():
                # Sanitize sheet names to strip out invalid characters
                safe_sheet = (
                    sheet.replace("/", "-")
                    .replace("\\", "-")
                    .replace("?", "")
                    .replace("*", "")
                    .replace("[", "")
                    .replace("]", "")
                    .replace(":", "")
                )
                # Ensure timezone info is removed from all datetime columns
                # as Excel formats cannot serialize timezone-aware datetime64 data
                for col in df.columns:
                    if pd.api.types.is_datetime64_any_dtype(df[col]):
                        if hasattr(df[col].dt, "tz") and df[col].dt.tz is not None:
                            df[col] = df[col].dt.tz_localize(None)
                    elif df[col].dtype == "object":
                        try:
                            non_null = df[col].dropna()
                            if not non_null.empty and hasattr(
                                non_null.iloc[0], "tzinfo"
                            ):
                                df[col] = pd.to_datetime(
                                    df[col], errors="coerce"
                                ).dt.tz_localize(None)
                        except:
                            pass
                # Save data frame to excel sheet, capping title to 31 chars
                df.to_excel(writer, sheet_name=safe_sheet[:31], index=False)
        output.seek(0)
        # Prepare streaming response download headers
        response = HttpResponse(
            output.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = (
            'attachment; filename="statistics_report.xlsx"'
        )
        return response
        
    # Format 2: CSV download (.csv)
    elif format == "csv":
        output = BytesIO()
        # Write each DataFrame block sequentially separated by headers
        for sheet, df in dfs.items():
            output.write(f"\n--- {sheet} ---\n".encode())
            df.to_csv(output, index=False)
        output.seek(0)
        response = HttpResponse(output.read(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="statistics_report.csv"'
        return response
        
    # Format 3: PDF download (.pdf)
    elif format == "pdf":
        try:
            from xhtml2pdf import pisa
        except ImportError:
            return HttpResponse("PDF export requires xhtml2pdf.", status=500)
        # Render the PDF template file to standard HTML string markup
        html = render_to_string(
            "reports/statistics_export_pdf.html",
            {
                "category_breakdown": category_breakdown,
                "month_labels": month_labels,
                "stock_in_by_month": stock_in_by_month,
                "stock_out_by_month": stock_out_by_month,
                "rental_status_breakdown": list(
                    rentals_qs.values("status").annotate(count=Count("id"))
                ),
                "rental_product_breakdown": list(
                    rentals_qs.values("product__name")
                    .annotate(count=Count("id"))
                    .order_by("-count")[:10]
                ),
                "alert_type_breakdown": list(
                    alerts_qs.values("alert_type").annotate(count=Count("id"))
                ),
                "alert_product_breakdown": list(
                    alerts_qs.values("product__name")
                    .annotate(count=Count("id"))
                    .order_by("-count")[:10]
                ),
            },
        )
        result = BytesIO()
        # Run Pisa parser to generate PDF buffer
        pisa.CreatePDF(html, dest=result)
        response = HttpResponse(result.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="statistics_report.pdf"'
        return response
        
    return HttpResponse("Invalid export format.", status=400)
