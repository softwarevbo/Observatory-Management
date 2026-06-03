import openpyxl
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create a sample bulk stock in Excel file."

    def handle(self, *args, **kwargs):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "StockIn"
        ws.append(["Product Name", "Quantity"])
        ws.append(["Laptop", 5])
        ws.append(["Mouse", 10])
        ws.append(["Keyboard", 7])
        wb.save("sample_stockin.xlsx")
        self.stdout.write(
            self.style.SUCCESS(
                "Sample bulk stock in Excel file created as sample_stockin.xlsx"
            )
        )
