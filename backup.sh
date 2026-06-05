#!/bin/bash

# Configuration
BACKUP_DIR="backups"
KEEP_BACKUPS=10
DB_FILE="db.sqlite3"
MEDIA_DIR="media"
BACKUP_CODE=true # Set to true to include all project source code in the backup

# Cloud Backup Configuration (Optional)
# To automatically upload backups to Google Drive, S3, Dropbox, etc.:
# 1. Install rclone: sudo apt-get install rclone
# 2. Configure a remote storage endpoint: rclone config (name it e.g. "mycloud")
# 3. Enter the remote path below (e.g. "mycloud:backups_folder")
RCLONE_REMOTE=""

# Define colors for output styling
GREEN='\033[0;32m'
NC='\033[0m' # No Color
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}        IIA Management System - Backup System   ${NC}"
echo -e "${BLUE}================================================${NC}"

# Get the directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
TEMP_DB_NAME="db_backup_${TIMESTAMP}.sqlite3"
TEMP_DB_PATH="$BACKUP_DIR/$TEMP_DB_NAME"
FINAL_ARCHIVE="$BACKUP_DIR/backup_${TIMESTAMP}.tar.gz"

echo -e "${GREEN}[*] Safely backing up database transactionally...${NC}"
# Use sqlite3 .backup to ensure transactional consistency
if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "$DB_FILE" ".backup '$TEMP_DB_PATH'"
else
    echo -e "${YELLOW}[!] Warning: sqlite3 CLI not found. Falling back to direct file copy (potential risk if database is currently being written to).${NC}"
    cp "$DB_FILE" "$TEMP_DB_PATH"
fi

if [ ! -f "$TEMP_DB_PATH" ]; then
    echo -e "${RED}[Error] Database backup failed! Exiting.${NC}"
    exit 1
fi

# Create a tar.gz archive containing:
# - The transactional SQLite database backup
# - The media/ folder (uploaded files)
# - Optionally the entire source code (excluding virtual environments, static files, and backups)
if [ "$BACKUP_CODE" = true ]; then
    echo -e "${GREEN}[*] Archiving database, media files, and source code into $FINAL_ARCHIVE...${NC}"
    tar --exclude="venv" --exclude=".venv" --exclude="staticfiles" --exclude="backups" --exclude=".git" --exclude="$DB_FILE" \
        -czf "$FINAL_ARCHIVE" -C "$DIR" . -C "$DIR/$BACKUP_DIR" "$TEMP_DB_NAME"
else
    echo -e "${GREEN}[*] Archiving database and media files into $FINAL_ARCHIVE...${NC}"
    tar -czf "$FINAL_ARCHIVE" -C "$DIR/$BACKUP_DIR" "$TEMP_DB_NAME" -C "$DIR" "$MEDIA_DIR"
fi

# Clean up temp database file from backups folder
rm "$TEMP_DB_PATH"

if [ -f "$FINAL_ARCHIVE" ]; then
    echo -e "${GREEN}[+] Backup created successfully:${NC}"
    echo -e "    📁 File: ${BLUE}$FINAL_ARCHIVE${NC}"
    echo -e "    ⚖️ Size: ${BLUE}$(du -h "$FINAL_ARCHIVE" | cut -f1)${NC}"
else
    echo -e "${RED}[Error] Archive creation failed!${NC}"
    exit 1
fi

# Rotate backups (keep only the last N)
echo -e "${GREEN}[*] Checking for old backups (keeping last $KEEP_BACKUPS)...${NC}"
BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/backup_*.tar.gz 2>/dev/null | wc -l)
if [ "$BACKUP_COUNT" -gt "$KEEP_BACKUPS" ]; then
    DELETE_COUNT=$((BACKUP_COUNT - KEEP_BACKUPS))
    echo -e "${YELLOW}[!] Rotating backups: Deleting $DELETE_COUNT older backup(s)...${NC}"
    # List backups sorted by modification time (oldest first) and delete the oldest ones
    ls -tr "$BACKUP_DIR"/backup_*.tar.gz | head -n "$DELETE_COUNT" | xargs rm -f
fi

# Cloud sync if configured
if [ -n "$RCLONE_REMOTE" ]; then
    echo -e "${GREEN}[*] Uploading backup to cloud storage ($RCLONE_REMOTE)...${NC}"
    if command -v rclone >/dev/null 2>&1; then
        rclone copy "$FINAL_ARCHIVE" "$RCLONE_REMOTE"
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}[+] Cloud upload successful!${NC}"
        else
            echo -e "${RED}[Error] Cloud upload failed!${NC}"
        fi
    else
        echo -e "${RED}[Error] rclone is not installed. Run 'sudo apt install rclone' to use cloud backup.${NC}"
    fi
fi

echo -e "${GREEN}[+] Backup rotation complete.${NC}"
echo -e "${BLUE}================================================${NC}"
