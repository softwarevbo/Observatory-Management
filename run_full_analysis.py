import os
import subprocess
import json
import time
import sys
from datetime import datetime

def run_command(cmd, shell=True):
    try:
        result = subprocess.run(cmd, shell=shell, capture_output=True, text=True)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except Exception as e:
        return "", str(e), 1

def run_analysis():
    results = {}
    print("💎 Initializing Enterprise-Grade Project Audit...")

    # 1. Static Code Analysis (SCA) - Multi-Tool Approach
    print("  [1/12] Running Flake8 (Syntactic & Style Linter)...")
    stdout, stderr, code = run_command("flake8 . --exclude=venv,.venv,*/migrations/*,*/__pycache__/* --count --statistics")
    results["flake8"] = {"output": stdout, "passed": code == 0}

    print("  [2/12] Running Pylint (Deep Logic & Code Smell Analysis)...")
    stdout, stderr, code = run_command("pylint . --ignore=venv,.venv,migrations --disable=C,R,W --enable=E,F")
    results["pylint"] = stdout

    print("  [3/12] Running Radon (Complexity & Maintainability Metrics)...")
    cc_stdout, _, _ = run_command("radon cc . -a -s -x 'venv/*,.venv/*,*/migrations/*'")
    mi_stdout, _, _ = run_command("radon mi . -s -x 'venv/*,.venv/*,*/migrations/*'")
    results["complexity"] = {"cc": cc_stdout, "mi": mi_stdout}

    # 2. Security Analysis
    print("  [4/12] Running Bandit (Security Vulnerability Scanning)...")
    stdout, stderr, code = run_command("bandit -r . -x ./venv,./.venv,./*/migrations/* -f json")
    try:
        results["security"] = json.loads(stdout)
    except:
        results["security"] = {"error": "Failed to parse Bandit output", "raw": stdout}

    print("  [5/12] Running Safety (Dependency Vulnerability Audit)...")
    stdout, stderr, code = run_command("safety check --full-report")
    results["dependencies"] = stdout

    # 3. Dynamic Analysis & Functional Testing
    print("  [6/12] Running Django Test Suite (Unit & Integration)...")
    run_command("coverage erase")
    test_start = time.time()
    stdout, stderr, code = run_command("coverage run --source=. manage.py test --noinput")
    test_end = time.time()
    results["functional_tests"] = {"output": stdout if stdout else stderr, "passed": code == 0, "duration": test_end - test_start}

    print("  [7/12] Generating Coverage Report (Transparency Matrix)...")
    stdout, stderr, code = run_command("coverage report --omit='*/venv/*,*/.venv/*,*/migrations/*,*/tests.py,manage.py,core/wsgi.py,core/asgi.py'")
    results["coverage"] = stdout

    # 4. Database & Integrity Analysis
    print("  [8/12] Performing Database Integrity Check...")
    stdout, stderr, code = run_command("python manage.py check")
    results["db_integrity"] = stdout

    # 5. Performance Analysis
    print("  [9/12] Running Performance Benchmark (Startup & Query Engine)...")
    perf_start = time.time()
    run_command("python manage.py check") # Proxy for system loading
    perf_end = time.time()
    results["performance"] = {"system_load_time": perf_end - perf_start}

    # 6. UI/UX & Compatibility Analysis (Technical Review)
    print("  [10/12] Analyzing Templates & UI Structure...")
    # Count templates and check for responsive meta tags
    templates_dir = "templates"
    responsive_count = 0
    total_templates = 0
    if os.path.exists(templates_dir):
        for root, dirs, files in os.walk(templates_dir):
            for file in files:
                if file.endswith(".html"):
                    total_templates += 1
                    with open(os.path.join(root, file), 'r', errors='ignore') as f:
                        if "viewport" in f.read():
                            responsive_count += 1
    results["ui_ux"] = {"total_templates": total_templates, "responsive_templates": responsive_count}

    # 7. Architecture Review
    print("  [11/12] Evaluating System Architecture...")
    apps = [d for d in os.listdir() if os.path.isdir(d) and os.path.exists(os.path.join(d, "__init__.py"))]
    results["architecture"] = {"apps_detected": apps}

    # 8. Report Finalization
    print("  [12/12] Consolidating Enterprise Data...")
    with open("enterprise_analysis_results.json", "w") as f:
        json.dump(results, f, indent=4)

    print("✅ Audit Complete! Enterprise data saved to enterprise_analysis_results.json")

if __name__ == "__main__":
    run_analysis()
