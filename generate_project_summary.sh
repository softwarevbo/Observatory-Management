#!/bin/bash

echo "=========================================="
echo "      PROJECT MODULARITY SUMMARY          "
echo "=========================================="
echo ""

apps=("products" "stock" "accounts" "reports" "procurement" "audit" "files" "inventory")

for app in "${apps[@]}"; do
    if [ -d "$app/views" ]; then
        echo "✅ App: $app"
        echo "   Structure: Modular Package"
        echo "   Modules:"
        ls "$app/views" | grep ".py" | grep -v "__init__.py" | sed 's/^/    - /'
        echo "------------------------------------------"
    else
        echo "❌ App: $app (Not modularized or directory missing)"
    fi
done

echo ""
echo "=========================================="
echo "      CODE STANDARDS CHECK (BLACK)        "
echo "=========================================="
black --check .
echo ""

echo "=========================================="
echo "      SYSTEM INTEGRITY CHECK              "
echo "=========================================="
python manage.py check
echo ""

echo "Done."
