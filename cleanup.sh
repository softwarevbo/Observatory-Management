#!/bin/bash

# ============================================
# FULL DJANGO RESET + CLEAN REBUILD SCRIPT
# ============================================

echo "========================================"
echo "DJANGO FULL RESET STARTED"
echo "========================================"

PROJECT_DIR="$(pwd)"

# --------------------------------------------
# 1. DELETE PYTHON CACHE
# --------------------------------------------

echo ""
echo "[1/10] Removing Python cache..."

find "$PROJECT_DIR" -type d -name "__pycache__" -exec rm -rf {} +
find "$PROJECT_DIR" -type f -name "*.pyc" -delete
find "$PROJECT_DIR" -type f -name "*.pyo" -delete
find "$PROJECT_DIR" -type f -name "*.pyd" -delete

echo "Python cache removed."

# --------------------------------------------
# 2. DELETE DJANGO CACHE
# --------------------------------------------

echo ""
echo "[2/10] Removing Django cache and temp files..."

find "$PROJECT_DIR" -type d -name ".pytest_cache" -exec rm -rf {} +
find "$PROJECT_DIR" -type d -name ".mypy_cache" -exec rm -rf {} +
find "$PROJECT_DIR" -type d -name ".ruff_cache" -exec rm -rf {} +
find "$PROJECT_DIR" -type d -name ".cache" -exec rm -rf {} +

find "$PROJECT_DIR" -type f -name "*.log" -delete
find "$PROJECT_DIR" -type f -name ".DS_Store" -delete

echo "Temporary files cleaned."

# --------------------------------------------
# 3. DELETE STATIC FILES
# --------------------------------------------

echo ""
echo "[3/10] Removing collected static files..."

if [ -d "staticfiles" ]; then
    rm -rf staticfiles/*
fi

echo "Staticfiles removed."

# --------------------------------------------
# 4. DELETE ALL MIGRATIONS
# --------------------------------------------

echo ""
echo "[4/10] Removing migrations..."

find . -path "*/migrations/*.py" ! -name "__init__.py" -delete
find . -path "*/migrations/*.pyc" -delete

echo "Migrations deleted."

# --------------------------------------------
# 5. DELETE DATABASE
# --------------------------------------------

echo ""
echo "[5/10] Removing database..."

find . -name "db.sqlite3" -delete
find . -name "*.sqlite3" -delete
find . -name "*.sqlite3-shm" -delete
find . -name "*.sqlite3-wal" -delete

echo "Database removed."

# --------------------------------------------
# 6. CREATE NEW MIGRATIONS
# --------------------------------------------

echo ""
echo "[6/10] Creating fresh migrations..."

python manage.py makemigrations

echo "Fresh migrations created."

# --------------------------------------------
# 7. APPLY MIGRATIONS
# --------------------------------------------

echo ""
echo "[7/10] Applying migrations..."

python manage.py migrate

echo "Database migrated."

# --------------------------------------------
# 8. COLLECT STATIC
# --------------------------------------------

echo ""
echo "[8/10] Collecting static files..."

python manage.py collectstatic --noinput

echo "Static files generated."

# --------------------------------------------
# 9. CLEAR SESSIONS
# --------------------------------------------

echo ""
echo "[9/10] Clearing sessions..."

python manage.py clearsessions

echo "Sessions cleared."

# --------------------------------------------
# 10. FINAL DJANGO CHECK
# --------------------------------------------

echo ""
echo "[10/10] Running Django system check..."

python manage.py check

echo ""
echo "========================================"
echo "DJANGO FULL RESET COMPLETED SUCCESSFULLY"
echo "========================================"