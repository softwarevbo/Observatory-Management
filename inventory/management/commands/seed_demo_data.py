"""
Management command to seed comprehensive demo/temp data for:
  - Inventory Management (branches, products, stock, adjustments, alerts, rentals, serials)
  - Project Management (projects, tasks, requirements, sprints, milestones)
"""
import random
import string
from datetime import date, timedelta, datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password

User = get_user_model()


class Command(BaseCommand):
    help = "Seeds comprehensive demo data for Inventory and Project Management"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing demo data before seeding",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🚀 Starting demo data seed..."))
        self._seed_inventory()
        self._seed_projects()
        self.stdout.write(self.style.SUCCESS("✅ Demo data seeding complete!"))

    # ─────────────────────────────────────────────
    # INVENTORY SEEDING
    # ─────────────────────────────────────────────
    def _seed_inventory(self):
        from products.models import Category, Product
        from inventory.models import (
            Branch, BranchStock, InventoryAdjustment, SerialNumber,
            Alert, Rental, InventoryUser, QuantityLimit
        )

        self.stdout.write("  📦 Seeding inventory data...")

        # ── Categories ───────────────────────────
        categories_data = [
            "Electronic Components", "Optical Instruments", "Mechanical Parts",
            "Computing Equipment", "Power Supplies", "Sensors & Detectors",
            "Cables & Connectors", "Measurement Tools", "Safety Equipment",
            "Laboratory Consumables",
        ]
        categories = {}
        for name in categories_data:
            cat, _ = Category.objects.get_or_create(name=name, defaults={"description": f"Category for {name}"})
            categories[name] = cat

        # ── Branches ─────────────────────────────
        branches_data = [
            ("HQ", "IIA Headquarters - Bengaluru", "Sarjapura Road, Bengaluru 560034", "+91-80-2553-0672"),
            ("KOR", "IIA Koramangala", "Koramangala 7th Block, Bengaluru 560095", "+91-80-2553-0680"),
            ("HOS", "IIA Hosakote Observatory", "Hosakote, Karnataka 562122", "+91-80-2799-4000"),
            ("HAN", "IIA Hanle Observatory", "Hanle, Ladakh 194303", "+91-01982-267042"),
            ("GBT", "IIA Gauribidanur", "Gauribidanur, Karnataka 561208", "+91-7760000001"),
        ]
        branches = []
        for code, name, address, phone in branches_data:
            branch, _ = Branch.objects.get_or_create(
                code=code,
                defaults={"name": name, "address": address, "contact_number": phone, "is_active": True}
            )
            branches.append(branch)

        # ── Inventory Users ───────────────────────
        inv_users = []
        inv_user_data = [
            ("inv_admin", "super_admin", branches[0]),
            ("inv_koramangala", "branch_admin", branches[1]),
            ("inv_hosakote", "branch_admin", branches[2]),
            ("inv_hanle", "branch_admin", branches[3]),
            ("inv_staff1", "staff", branches[0]),
            ("inv_staff2", "staff", branches[1]),
        ]
        for uname, role, branch in inv_user_data:
            iuser, created = InventoryUser.objects.get_or_create(
                username=uname,
                defaults={
                    "password": make_password("demo123"),
                    "role": role,
                    "branch": branch,
                    "email": f"{uname}@iiap.res.in",
                    "is_active": True,
                    "can_view_all_branches_inventory": role == "super_admin",
                    "can_manage_users": role == "super_admin",
                }
            )
            inv_users.append(iuser)

        admin_user = inv_users[0]

        # ── Products ─────────────────────────────
        products_data = [
            # (name, category, brand, price, sku, unit, status, supplier)
            ("CCD Detector - 4096x4096", "Sensors & Detectors", "Andor", 15000.00, "SKU-CCD-4096", "Units", "in_stock", "Andor Technology"),
            ("Astronomical Telescope Mount (EQ6-R)", "Optical Instruments", "Sky-Watcher", 2500.00, "SKU-EQ6R-01", "Units", "in_stock", "Orion Telescopes"),
            ("Raspberry Pi 4B - 8GB", "Electronic Components", "Raspberry Pi", 85.00, "SKU-RPI4B-8G", "Units", "in_stock", "Farnell"),
            ("NVIDIA RTX 4090 GPU", "Computing Equipment", "NVIDIA", 1800.00, "SKU-RTX4090-01", "Units", "low_stock", "NVIDIA Direct"),
            ("Dell PowerEdge R750 Server", "Computing Equipment", "Dell", 8500.00, "SKU-DELL-R750", "Units", "in_stock", "Dell India"),
            ("Zeiss Binoculars 20x60", "Optical Instruments", "Zeiss", 1200.00, "SKU-ZEISS-2060", "Units", "in_stock", "Zeiss Vision Care"),
            ("Arduino Mega 2560", "Electronic Components", "Arduino", 45.00, "SKU-ARD-MEGA", "Units", "in_stock", "Arduino Official"),
            ("Solar Panel 400W Mono", "Power Supplies", "Tata Solar", 350.00, "SKU-SOL-400W", "Units", "in_stock", "Tata Power Solar"),
            ("UPS 10KVA Online", "Power Supplies", "APC", 3200.00, "SKU-UPS-10KVA", "Units", "in_stock", "Schneider Electric"),
            ("Multimeter Fluke 87V", "Measurement Tools", "Fluke", 480.00, "SKU-FLK-87V", "Units", "in_stock", "Fluke Corporation"),
            ("Oscilloscope Keysight DSOX1204G", "Measurement Tools", "Keysight", 950.00, "SKU-KEY-1204G", "Units", "in_stock", "Keysight Technologies"),
            ("Fiber Optic Cable 100m (Single Mode)", "Cables & Connectors", "Corning", 120.00, "SKU-FOC-SM100", "Meters", "in_stock", "Corning India"),
            ("RJ45 Cat6 Patch Panel 48-Port", "Cables & Connectors", "Panduit", 280.00, "SKU-PP-CAT6-48", "Units", "in_stock", "Panduit Corp"),
            ("Photodiode Array - 128 elements", "Sensors & Detectors", "Hamamatsu", 2200.00, "SKU-PDA-128", "Units", "low_stock", "Hamamatsu Photonics"),
            ("Helium Neon Laser 5mW", "Optical Instruments", "Melles Griot", 750.00, "SKU-HeNe-5mW", "Units", "in_stock", "Melles Griot"),
            ("Anti-Vibration Table 90x60cm", "Laboratory Consumables", "Newport", 3800.00, "SKU-AVT-9060", "Units", "in_stock", "Newport Corporation"),
            ("FPGA Board - Xilinx Zynq 7000", "Electronic Components", "Xilinx", 620.00, "SKU-XLX-ZY7K", "Units", "in_stock", "Avnet"),
            ("Cryostat Liquid Nitrogen Dewar 50L", "Laboratory Consumables", "Thermo Fisher", 1400.00, "SKU-CRYO-50L", "Units", "in_stock", "Thermo Fisher Scientific"),
            ("High Resolution Spectrograph Grating", "Optical Instruments", "Richardson Gratings", 5500.00, "SKU-HRG-7200", "Units", "in_stock", "MKS Instruments"),
            ("Network Switch 48-Port Cisco", "Computing Equipment", "Cisco", 1800.00, "SKU-CSC-SW48", "Units", "in_stock", "Cisco Systems India"),
            ("Weather Station Davis Vantage Pro2", "Sensors & Detectors", "Davis Instruments", 890.00, "SKU-DAV-VP2", "Units", "in_stock", "Davis Instruments"),
            ("3D Printer Bambu Lab X1 Carbon", "Mechanical Parts", "Bambu Lab", 1500.00, "SKU-BML-X1C", "Units", "in_stock", "Bambu Lab"),
            ("Vacuum Pump Rotary Vane 100L/min", "Laboratory Consumables", "Edwards", 2200.00, "SKU-EDW-VAC100", "Units", "in_stock", "Edwards Vacuum"),
            ("Servo Motor 400W Mitsubishi", "Mechanical Parts", "Mitsubishi", 380.00, "SKU-MIT-SM400", "Units", "in_stock", "Mitsubishi Electric"),
            ("Ethernet Cable Cat6A 1000m Spool", "Cables & Connectors", "Belden", 450.00, "SKU-BEL-CAT6A", "Meters", "in_stock", "Belden"),
            ("Spare Dome Drive Motor (60cm telescope)", "Mechanical Parts", "Custom", 1800.00, "SKU-DDM-60CM", "Units", "in_stock", "Local Vendor"),
            ("Thermal Camera FLIR E8-XT", "Sensors & Detectors", "FLIR", 3400.00, "SKU-FLIR-E8", "Units", "low_stock", "Teledyne FLIR"),
            ("High Power LED Calibration Lamp", "Optical Instruments", "Thorlabs", 320.00, "SKU-THR-HPLED", "Units", "in_stock", "Thorlabs"),
            ("PCIe SSD 2TB Samsung 990 Pro", "Computing Equipment", "Samsung", 220.00, "SKU-SSD-990P2T", "Units", "in_stock", "Samsung India"),
            ("Signal Generator Keysight 33500B", "Measurement Tools", "Keysight", 2800.00, "SKU-KEY-33500B", "Units", "out_of_stock", "Keysight Technologies"),
        ]

        products = []
        for i, (name, cat_name, brand, price, sku, unit, status, supplier) in enumerate(products_data):
            prod, _ = Product.objects.get_or_create(
                sku=sku,
                defaults={
                    "name": name,
                    "category": categories[cat_name],
                    "branch": branches[i % len(branches)],
                    "brand": brand,
                    "price": Decimal(str(price)),
                    "unit": unit,
                    "status": status,
                    "supplier": supplier,
                    "description": f"High-quality {name} used in astronomical research and observatory operations.",
                    "purchase_details": f"Purchased from {supplier}. Invoice available in procurement records.",
                }
            )
            products.append(prod)

        # ── Branch Stock ──────────────────────────
        stock_quantities = [
            # Each product gets stock across multiple branches
            # (product_idx, branch_idx, current_qty, reserved_qty, rack, shelf)
        ]
        for prod_idx, prod in enumerate(products):
            for branch_idx, branch in enumerate(branches):
                # Skip some combinations to make it realistic
                if random.random() < 0.3:
                    continue
                qty = random.randint(1, 50)
                reserved = random.randint(0, min(5, qty))
                low_limit = random.randint(2, 8)
                BranchStock.objects.get_or_create(
                    branch=branch,
                    product=prod,
                    defaults={
                        "current_quantity": qty,
                        "reserved_quantity": reserved,
                        "rack_number": f"R{random.randint(1, 10):02d}",
                        "shelf_number": f"S{random.choice('ABCDE')}{random.randint(1,5)}",
                        "local_sku": f"{branch.code}-{prod.sku}",
                        "low_stock_limit": low_limit,
                    }
                )

        # ── Inventory Adjustments ─────────────────
        adj_reasons = [
            "Received from supplier", "Damaged during transit", "Returned by borrower",
            "Annual stock audit correction", "Lost during relocation", "Calibration unit removed",
            "New procurement batch", "Transferred to HAN Observatory", "Lab usage consumption",
        ]
        for _ in range(60):
            prod = random.choice(products)
            branch = random.choice(branches)
            qty = random.randint(-5, 20)
            days_ago = random.randint(1, 180)
            adj = InventoryAdjustment(
                product=prod,
                branch=branch,
                adjustment_type=random.choice(["manual", "automated"]),
                quantity=qty,
                reason=random.choice(adj_reasons),
                created_by=random.choice(inv_users),
            )
            adj.save()
            # Backdate the timestamp
            InventoryAdjustment.objects.filter(pk=adj.pk).update(
                timestamp=timezone.now() - timedelta(days=days_ago)
            )

        # ── Alerts ───────────────────────────────
        alert_types = ["low_stock", "out_of_stock", "limit_reached"]
        alert_statuses = ["active", "acknowledged", "resolved"]
        alert_messages = [
            "Stock level critically low. Immediate reorder required.",
            "Product has reached zero quantity. Operations may be impacted.",
            "Quantity has crossed configured limit threshold.",
            "Emergency restock needed for ongoing telescope maintenance.",
            "Consumable supply running out. Please initiate procurement.",
        ]
        for i in range(25):
            prod = random.choice(products)
            branch = random.choice(branches)
            atype = random.choice(alert_types)
            astatus = random.choice(alert_statuses)
            Alert.objects.get_or_create(
                product=prod,
                branch=branch,
                alert_type=atype,
                defaults={
                    "status": astatus,
                    "message": random.choice(alert_messages),
                    "current_quantity": random.randint(0, 5),
                    "limit_quantity": random.randint(3, 10),
                    "acknowledged_by": random.choice(inv_users) if astatus != "active" else None,
                    "resolved_by": random.choice(inv_users) if astatus == "resolved" else None,
                }
            )

        # ── Serial Numbers ────────────────────────
        serial_statuses = ["available", "sold", "returned", "damaged"]
        for prod in products[:15]:
            for j in range(random.randint(2, 6)):
                sn = f"SN-{prod.sku[-6:]}-{j+1:04d}"
                branch = random.choice(branches)
                SerialNumber.objects.get_or_create(
                    serial_number=sn,
                    defaults={
                        "product": prod,
                        "branch": branch,
                        "status": random.choice(serial_statuses),
                    }
                )

        # ── Rentals ───────────────────────────────
        renters = [
            "Prof. K. Subramanian - TIFR Mumbai",
            "Dr. Anand Narayan - IISc Bangalore",
            "Mr. Suresh Babu - ISRO Satellite Centre",
            "Dr. Priya Nair - RRI Bangalore",
            "Prof. Venkataramaiah - Osmania University",
            "Dr. Sushil Kumar - PRL Ahmedabad",
            "Ms. Deepa Murugan - NCRA Pune",
            "Mr. Rajiv Chandrashekar - IIT Madras",
        ]
        rental_reasons = [
            "Conference demonstration", "Inter-institute collaborative project",
            "Short-term repair and calibration", "Research visit equipment loan",
            "Observatory maintenance assistance", "Student training programme",
        ]
        rental_statuses = ["active", "returned", "overdue"]
        for i in range(20):
            prod = random.choice(products[:20])
            branch = random.choice(branches)
            start = date.today() - timedelta(days=random.randint(10, 120))
            return_d = start + timedelta(days=random.randint(7, 60))
            status = random.choice(rental_statuses)
            Rental.objects.create(
                product=prod,
                branch=branch,
                quantity=random.randint(1, 3),
                rented_to=random.choice(renters),
                reason=random.choice(rental_reasons),
                rental_date=start,
                rental_time=datetime.now().time(),
                return_date=return_d,
                status=status,
                created_by=random.choice(inv_users),
            )

        # ── Quantity Limits ───────────────────────
        for prod in products[:20]:
            for branch in branches[:3]:
                QuantityLimit.objects.get_or_create(
                    product=prod,
                    branch=branch,
                    defaults={
                        "limit_quantity": random.randint(3, 15),
                        "is_active": True,
                        "created_by": admin_user,
                    }
                )

        self.stdout.write(self.style.SUCCESS(f"    ✓ Inventory: {len(products)} products, {len(branches)} branches seeded"))

    # ─────────────────────────────────────────────
    # PROJECT MANAGEMENT SEEDING
    # ─────────────────────────────────────────────
    def _seed_projects(self):
        from tasks.models import (
            Project, Task, ProjectModule, Requirement, Sprint,
            Release
        )

        self.stdout.write("  📊 Seeding project management data...")

        users = list(User.objects.all()[:10])
        if not users:
            self.stdout.write(self.style.WARNING("    No users found. Skipping project seeding."))
            return

        creator = users[0]

        # ── Projects ─────────────────────────────
        projects_data = [
            {
                "name": "GROWTH-India Telescope Control System",
                "module": "software",
                "status": "active",
                "priority": "critical",
                "description": "Real-time control software for the GROWTH-India telescope at Hanle, Ladakh. Includes automated scheduling, alert follow-up, and data pipeline integration.",
                "progress": 72,
                "bg": "#0f172a", "btn": "#6366f1",
                "start": date.today() - timedelta(days=180),
                "end": date.today() + timedelta(days=90),
            },
            {
                "name": "Solar Coronagraph Data Reduction Pipeline",
                "module": "software",
                "status": "active",
                "priority": "high",
                "description": "Automated pipeline for reducing coronagraph observations from VELC (ADITYA-L1). Handles FITS processing, calibration, and archiving.",
                "progress": 55,
                "bg": "#0c1a2e", "btn": "#f59e0b",
                "start": date.today() - timedelta(days=120),
                "end": date.today() + timedelta(days=150),
            },
            {
                "name": "Telescope Dome Automation - HOS",
                "module": "electronics",
                "status": "active",
                "priority": "high",
                "description": "Automated dome control system for Hosakote Observatory 60cm telescope. Includes weather monitoring integration and safety interlocks.",
                "progress": 88,
                "bg": "#1a1035", "btn": "#a855f7",
                "start": date.today() - timedelta(days=240),
                "end": date.today() + timedelta(days=30),
            },
            {
                "name": "Multi-Object Spectrograph Electronics",
                "module": "electronics",
                "status": "planning",
                "priority": "medium",
                "description": "Design and fabrication of electronics subsystem for the proposed multi-object spectrograph at 2.34m VBT Kavalur.",
                "progress": 20,
                "bg": "#0d1f0d", "btn": "#22c55e",
                "start": date.today() - timedelta(days=30),
                "end": date.today() + timedelta(days=300),
            },
            {
                "name": "IRSF Telescope Mirror Coating Project",
                "module": "mechanical",
                "status": "completed",
                "priority": "high",
                "description": "Full re-aluminization of the primary and secondary mirrors of the 1.4m IRSF telescope at SAAO, South Africa.",
                "progress": 100,
                "bg": "#1a0a00", "btn": "#f97316",
                "start": date.today() - timedelta(days=365),
                "end": date.today() - timedelta(days=60),
            },
            {
                "name": "Adaptive Optics Simulation Platform",
                "module": "simulation",
                "status": "active",
                "priority": "medium",
                "description": "End-to-end simulation tool for adaptive optics systems using Python and MATLAB. Includes atmospheric turbulence modeling.",
                "progress": 40,
                "bg": "#0a1a2a", "btn": "#0ea5e9",
                "start": date.today() - timedelta(days=90),
                "end": date.today() + timedelta(days=180),
            },
            {
                "name": "HAN Observatory Network Upgrade",
                "module": "software",
                "status": "on_hold",
                "priority": "medium",
                "description": "Upgrade network infrastructure at Hanle Observatory to support real-time data transfer of 10Gbps. Includes dark fiber installation and VPN setup.",
                "progress": 35,
                "bg": "#1a1500", "btn": "#eab308",
                "start": date.today() - timedelta(days=150),
                "end": date.today() + timedelta(days=120),
            },
            {
                "name": "NIR Photometry Pipeline for TANSPEC",
                "module": "software",
                "status": "active",
                "priority": "high",
                "description": "Near-infrared photometry reduction pipeline for TANSPEC instrument on the 3.6m DOT at Devasthal. Python-based with IRAF legacy support.",
                "progress": 62,
                "bg": "#0d0a1f", "btn": "#8b5cf6",
                "start": date.today() - timedelta(days=200),
                "end": date.today() + timedelta(days=60),
            },
            {
                "name": "IIA Website Redesign & Portal",
                "module": "software",
                "status": "active",
                "priority": "low",
                "description": "Complete redesign of the IIA public website with a modern portal for staff, preprint submissions, telescope time proposals, and news.",
                "progress": 45,
                "bg": "#1a0a1a", "btn": "#ec4899",
                "start": date.today() - timedelta(days=60),
                "end": date.today() + timedelta(days=120),
            },
            {
                "name": "Optical Bench Characterization Lab",
                "module": "optics",
                "status": "completed",
                "priority": "low",
                "description": "Setup and characterization of optical bench for testing fiber optic components used in MFOSC-P spectrograph.",
                "progress": 100,
                "bg": "#001a1a", "btn": "#14b8a6",
                "start": date.today() - timedelta(days=300),
                "end": date.today() - timedelta(days=100),
            },
        ]

        created_projects = []
        for pd in projects_data:
            proj, created = Project.objects.get_or_create(
                name=pd["name"],
                defaults={
                    "description": pd["description"],
                    "module": pd["module"],
                    "status": pd["status"],
                    "priority": pd["priority"],
                    "background_color": pd["bg"],
                    "button_color": pd["btn"],
                    "start_date": pd["start"],
                    "end_date": pd["end"],
                    "created_by": creator,
                    "progress": pd["progress"],
                    "visibility": "public",
                }
            )
            if created:
                proj.members.set(users[:min(5, len(users))])
                proj.managers.set(users[:2])
                proj.project_incharge = users[0]
                proj.save()
            created_projects.append(proj)

        # ── Project Modules ───────────────────────
        module_names = ["Backend", "Frontend", "Hardware", "Testing", "Documentation", "Integration", "Deployment"]
        for proj in created_projects:
            for mname in random.sample(module_names, random.randint(2, 5)):
                ProjectModule.objects.get_or_create(
                    project=proj,
                    name=mname,
                    defaults={"description": f"{mname} module for {proj.name}"}
                )

        # ── Tasks ─────────────────────────────────
        task_templates = [
            ("Implement WebSocket real-time event handler", "feature", "in_progress", "critical"),
            ("Fix memory leak in data acquisition thread", "bug", "review", "high"),
            ("Write unit tests for calibration module", "task", "todo", "medium"),
            ("Design database schema for observation logs", "task", "done", "high"),
            ("Create REST API for telescope pointing commands", "feature", "done", "critical"),
            ("Integrate weather station data feed", "feature", "in_progress", "high"),
            ("Performance profiling of image processing pipeline", "research", "todo", "medium"),
            ("Update FITS header documentation", "task", "done", "low"),
            ("Fix incorrect coordinate transformation bug", "bug", "done", "critical"),
            ("Deploy staging environment on cloud VM", "task", "in_progress", "high"),
            ("Implement auto-guiding feedback loop", "feature", "todo", "high"),
            ("Calibrate photometric standard star database", "task", "review", "medium"),
            ("Write API documentation using Swagger", "task", "todo", "low"),
            ("Add dark frame subtraction to pipeline", "improvement", "done", "medium"),
            ("Fix GUI freeze on large dataset load", "bug", "in_progress", "high"),
            ("Research GPU acceleration options for FFT", "research", "done", "medium"),
            ("Implement logging and error reporting", "improvement", "done", "low"),
            ("Test fiber optic signal integrity at -20C", "task", "review", "high"),
            ("Model thermal expansion of CCD mount", "task", "todo", "medium"),
            ("Validate dome encoder feedback loop", "task", "done", "critical"),
            ("Setup CI/CD pipeline with GitHub Actions", "task", "done", "medium"),
            ("Optimize database queries for report generation", "improvement", "in_progress", "high"),
            ("Implement user role-based access control", "feature", "done", "high"),
            ("Design PCB for signal conditioning board", "task", "in_progress", "high"),
            ("Write data backup and recovery procedures", "task", "todo", "medium"),
            ("Test communication protocol with dome controller", "task", "done", "high"),
            ("Create simulation model for atmospheric seeing", "research", "in_progress", "medium"),
            ("Implement spectral order extraction algorithm", "feature", "review", "critical"),
            ("Document hardware assembly procedure", "task", "done", "low"),
            ("Performance test under high-altitude conditions", "task", "todo", "high"),
            ("Refactor legacy FORTRAN code to Python", "improvement", "in_progress", "medium"),
            ("Add multi-language support to UI", "feature", "todo", "low"),
            ("Integrate FITS viewer in web portal", "feature", "in_progress", "medium"),
            ("Migrate database from SQLite to PostgreSQL", "task", "todo", "high"),
            ("Write FPGA firmware for ADC interface", "feature", "review", "critical"),
            ("Test emergency shutdown interlock sequence", "task", "done", "critical"),
            ("Analyze SNR of detector readout noise", "research", "done", "medium"),
            ("Implement 2D Gaussian fitting for PSF analysis", "feature", "in_progress", "high"),
            ("Fix timezone handling in observation scheduler", "bug", "done", "high"),
            ("Add email notification for pipeline failures", "improvement", "done", "medium"),
        ]

        priorities = ["low", "medium", "high", "critical"]
        statuses = ["todo", "in_progress", "review", "done", "blocked"]

        for proj in created_projects:
            proj_modules = list(proj.modules.all())
            task_count = random.randint(8, 18)
            used_tasks = random.sample(task_templates, min(task_count, len(task_templates)))
            for i, (title, ttype, status, priority) in enumerate(used_tasks):
                module = proj_modules[i % len(proj_modules)] if proj_modules else None
                due = date.today() + timedelta(days=random.randint(-30, 60))
                task, _ = Task.objects.get_or_create(
                    project=proj,
                    title=title,
                    defaults={
                        "description": f"Detailed task for: {title}. This involves planning, implementation, and testing phases.",
                        "task_type": ttype,
                        "status": status,
                        "priority": priority,
                        "module": module,
                        "due_date": due,
                        "story_points": random.choice([1, 2, 3, 5, 8, 13]),
                        "estimated_hours": Decimal(str(random.randint(2, 40))),
                        "actual_hours": Decimal(str(random.randint(1, 35))) if status == "done" else None,
                        "created_by": creator,
                        "tags": random.choice(["backend,api", "frontend,ui", "hardware,electronics", "testing,qa", "research,analysis", ""]),
                        "is_approved": status == "done",
                    }
                )
                if users:
                    task.assignees.set(random.sample(users, min(2, len(users))))

        # ── Requirements ──────────────────────────
        req_templates = [
            ("System shall achieve pointing accuracy of < 1 arcsec RMS", "functional", "approved"),
            ("User authentication via LDAP or local accounts", "security", "approved"),
            ("Data pipeline must process 1 GB FITS files within 60 seconds", "non_functional", "review"),
            ("REST API endpoints must return JSON within 200ms", "api", "approved"),
            ("System must support simultaneous connections from 10 remote users", "technical", "draft"),
            ("Interface shall display real-time CCD temperature monitoring", "uiux", "approved"),
            ("Database backup must run nightly and retain 30 days history", "database", "approved"),
            ("Observatory control must remain functional during network outages", "functional", "review"),
            ("All safety interlocks must engage within 2 seconds of trigger", "functional", "approved"),
            ("System shall log all operator commands with timestamp and username", "technical", "implemented"),
            ("Telescope scheduler must optimize for minimum slew time", "functional", "implemented"),
            ("Web portal shall be mobile-responsive (Bootstrap/Tailwind)", "uiux", "draft"),
            ("Instrument change-over time must be under 10 minutes", "functional", "approved"),
            ("Pipeline output files must conform to FITS standard v3.0", "technical", "verified"),
            ("System must provide API for external time-request submissions", "api", "review"),
        ]
        for proj in created_projects[:6]:
            proj_modules = list(proj.modules.all())
            for i, (name, rtype, rstatus) in enumerate(random.sample(req_templates, min(8, len(req_templates)))):
                module = proj_modules[i % len(proj_modules)] if proj_modules else None
                Requirement.objects.get_or_create(
                    project=proj,
                    name=name,
                    defaults={
                        "description": f"Requirement: {name}",
                        "requirement_type": rtype,
                        "status": rstatus,
                        "priority": random.choice(["low", "medium", "high", "critical"]),
                        "module": module,
                        "created_by": creator,
                        "is_approved": rstatus in ["approved", "implemented", "verified"],
                    }
                )

        # ── Sprints ───────────────────────────────
        try:
            for proj in created_projects[:5]:
                for s_num in range(1, random.randint(3, 6)):
                    s_start = proj.start_date + timedelta(weeks=(s_num - 1) * 2) if proj.start_date else date.today() - timedelta(weeks=s_num * 2)
                    s_end = s_start + timedelta(weeks=2)
                    is_completed = s_end < date.today()
                    is_active = s_start <= date.today() <= s_end
                    Sprint.objects.get_or_create(
                        project=proj,
                        name=f"Sprint {s_num}",
                        defaults={
                            "goal": f"Deliver sprint {s_num} deliverables for {proj.name}",
                            "start_date": s_start,
                            "end_date": s_end,
                            "is_active": is_active,
                            "is_completed": is_completed,
                        }
                    )
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"    Sprint seeding skipped: {e}"))

        # ── Releases ─────────────────────────────
        try:
            release_data = [
                ("v0.1.0 Alpha", "partial", "completed", "v0.1.0", "Initial alpha release with core telescope control commands."),
                ("v0.5.0 Beta", "partial", "completed", "v0.5.0", "Beta release including GUI and basic scheduler."),
                ("v1.0.0 Phase 1 Release", "phase", "active", "v1.0.0", "First major phase release. Full dome automation, weather integration."),
                ("v1.1.0 Patch", "partial", "planning", "v1.1.0", "Patch release fixing memory leak and adding dark frame subtraction."),
            ]
            for proj in created_projects[:4]:
                for rname, rtype, rstatus, tag, desc in release_data[:random.randint(1, 4)]:
                    try:
                        Release.objects.get_or_create(
                            project=proj,
                            name=rname,
                            defaults={
                                "release_type": rtype,
                                "status": rstatus,
                                "description": desc,
                                "tag_name": tag,
                                "version": tag.lstrip("v"),
                                "author": creator,
                                "is_approved": rstatus == "completed",
                                "target_date": date.today() + timedelta(days=random.randint(30, 180)),
                            }
                        )
                    except Exception:
                        pass
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"    Release seeding skipped: {e}"))

        total_tasks = Task.objects.count()
        total_projects = Project.objects.count()
        self.stdout.write(self.style.SUCCESS(f"    ✓ Projects: {total_projects} projects, {total_tasks} tasks seeded"))
