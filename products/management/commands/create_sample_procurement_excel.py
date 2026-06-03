import openpyxl
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create a sample procurement Excel file."

    def handle(self, *args, **kwargs):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Procurement"
        ws.append(["Product Name", "Requested Quantity"])
        ws.append(["Laptop", 10])
        ws.append(["Mouse", 5])
        ws.append(["Keyboard", 3])
        ws.append(["Monitor", 2])
        wb.save("sample_procurement.xlsx")
        self.stdout.write(
            self.style.SUCCESS(
                "Sample procurement Excel file created as sample_procurement.xlsx"
            )
        )
