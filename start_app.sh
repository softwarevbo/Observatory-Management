#!/bin/bash

# Define colors for output styling
GREEN='\033[0;32m'
NC='\033[0m' # No Color
BLUE='\033[0;34m'
YELLOW='\033[1;33m'

echo -e "${BLUE}==============================================${NC}"
echo -e "${BLUE}    IIA Management System - Local Launcher    ${NC}"
echo -e "${BLUE}==============================================${NC}"

# Get the directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Check if .venv exists, otherwise check venv
if [ -d ".venv" ]; then
    echo -e "${GREEN}[*] Activating virtual environment (.venv)...${NC}"
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo -e "${GREEN}[*] Activating virtual environment (venv)...${NC}"
    source venv/bin/activate
else
    echo -e "${YELLOW}[!] Warning: Virtual environment not found. Running with system python.${NC}"
fi

# Run database migrations
echo -e "${GREEN}[*] Applying database migrations...${NC}"
python manage.py migrate

# Collect static files
echo -e "${GREEN}[*] Collecting static files locally...${NC}"
python manage.py collectstatic --noinput

# Launch browser in background after server starts
echo -e "${GREEN}[*] Launching browser at http://127.0.0.1:8000/...${NC}"
(
    sleep 2
    if command -v xdg-open > /dev/null; then
        xdg-open http://127.0.0.1:8000/ > /dev/null 2>&1
    elif command -v google-chrome > /dev/null; then
        google-chrome http://127.0.0.1:8000/ > /dev/null 2>&1
    elif command -v firefox > /dev/null; then
        firefox http://127.0.0.1:8000/ > /dev/null 2>&1
    fi
) &

# Print LAN IP addresses for access
echo -e "${YELLOW}[*] Detecting LAN IP addresses...${NC}"
ips=$(hostname -I)
for ip in $ips; do
    if [[ ! $ip =~ ^127\. ]]; then
        echo -e "    👉  Access on LAN: ${GREEN}http://${ip}:8000/${NC}"
    fi
done

# Start Django development server
echo -e "${GREEN}[*] Starting local Django web server on 0.0.0.0:8000...${NC}"
python manage.py runserver 0.0.0.0:8000
