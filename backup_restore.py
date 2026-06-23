import os
import sys
import shutil
import hashlib
import zipfile
import argparse
from datetime import datetime

# Configuration
BACKUP_DIR = "backups"
KEEP_BACKUPS = 10
DB_FILE = "db.sqlite3"
MEDIA_DIR = "media"

# Color constants for terminal formatting
GREEN = '\033[92m'
BLUE = '\033[94m'
YELLOW = '\033[93m'
RED = '\033[91m'
BOLD = '\033[1m'
NC = '\033[0m'  # Reset Color

def print_banner():
    print(f"{BLUE}===================================================={NC}")
    print(f"{BLUE}{BOLD}     IIAP OM & IM - Secure Backup & Restore Tool    {NC}")
    print(f"{BLUE}===================================================={NC}")

def compute_sha256(file_path):
    """Computes SHA-256 hash of a file for integrity checks."""
    sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception as e:
        print(f"{RED}[Error] Failed to compute hash: {e}{NC}")
        return None

def transaction_safe_db_backup(src_db, dest_db):
    """Performs a transaction-safe hot copy of the SQLite database."""
    try:
        import sqlite3
        src = sqlite3.connect(src_db)
        dst = sqlite3.connect(dest_db)
        with dst:
            src.backup(dst)
        dst.close()
        src.close()
        return True
    except Exception as e:
        print(f"{YELLOW}[!] Warning: Online database backup failed ({e}). Falling back to file copy...{NC}")
        try:
            shutil.copy2(src_db, dest_db)
            return True
        except Exception as copy_err:
            print(f"{RED}[Error] Fallback file copy also failed: {copy_err}{NC}")
            return False

def rotate_backups():
    """Rotates older backups, keeping only the last KEEP_BACKUPS archives."""
    print(f"{GREEN}[*] Checking for old backups (keeping last {KEEP_BACKUPS})...{NC}")
    if not os.path.exists(BACKUP_DIR):
        return
    
    # Get list of backup zip files
    files = [os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if f.startswith("backup_") and f.endswith(".zip")]
    files.sort(key=os.path.getmtime)  # Sort oldest first
    
    if len(files) > KEEP_BACKUPS:
        to_delete = files[:-KEEP_BACKUPS]
        for f in to_delete:
            try:
                os.remove(f)
                hash_file = f + ".sha256"
                if os.path.exists(hash_file):
                    os.remove(hash_file)
                print(f"{YELLOW}[!] Deleted old backup: {os.path.basename(f)}{NC}")
            except Exception as e:
                print(f"{RED}[Error] Failed to delete old backup {f}: {e}{NC}")

def run_backup():
    """Creates a secure transactional backup including database, media, and SHA-256 hash verification."""
    print_banner()
    
    # Ensure backups folder exists
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    # Check that core paths exist
    if not os.path.exists(DB_FILE):
        print(f"{RED}[Error] Database file '{DB_FILE}' not found! Aborting backup.{NC}")
        return False
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_db_name = f"db_backup_{timestamp}.sqlite3"
    temp_db_path = os.path.join(BACKUP_DIR, temp_db_name)
    archive_name = f"backup_{timestamp}.zip"
    archive_path = os.path.join(BACKUP_DIR, archive_name)
    
    print(f"{GREEN}[*] Safely backing up database transactionally...{NC}")
    if not transaction_safe_db_backup(DB_FILE, temp_db_path):
        print(f"{RED}[Error] Database backup failed!{NC}")
        return False
        
    print(f"{GREEN}[*] Compressing database and media files into {archive_path}...{NC}")
    try:
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 1. Archive the database file (at the root of zip)
            zipf.write(temp_db_path, arcname=DB_FILE)
            
            # 2. Archive the media files
            if os.path.exists(MEDIA_DIR):
                for root, dirs, files in os.walk(MEDIA_DIR):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # Compute relative path to store in archive
                        rel_path = os.path.relpath(file_path, os.path.dirname(MEDIA_DIR))
                        zipf.write(file_path, arcname=rel_path)
            else:
                print(f"{YELLOW}[!] Warning: Media folder '{MEDIA_DIR}' does not exist. Backing up database only.{NC}")
    except Exception as e:
        print(f"{RED}[Error] Archiving failed: {e}{NC}")
        if os.path.exists(archive_path):
            os.remove(archive_path)
        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)
        return False
        
    # Clean up temp database file
    if os.path.exists(temp_db_path):
        os.remove(temp_db_path)
        
    # Calculate secure hash
    print(f"{GREEN}[*] Generating secure SHA-256 integrity hash...{NC}")
    file_hash = compute_sha256(archive_path)
    if not file_hash:
        print(f"{RED}[Error] Hash generation failed! Removing invalid archive.{NC}")
        if os.path.exists(archive_path):
            os.remove(archive_path)
        return False
        
    # Write hash to .sha256 file
    hash_file_path = archive_path + ".sha256"
    with open(hash_file_path, "w") as hf:
        hf.write(file_hash)
        
    size_mb = os.path.getsize(archive_path) / (1024 * 1024)
    print(f"{GREEN}[+] Backup created successfully!{NC}")
    print(f"    [+] File: {BLUE}{archive_path}{NC}")
    print(f"    [*] Size: {BLUE}{size_mb:.2f} MB{NC}")
    print(f"    [#] SHA-256 Hash: {BLUE}{file_hash}{NC}")
    
    # Rotate old backups
    rotate_backups()
    print(f"{BLUE}===================================================={NC}")
    return True

def run_restore(archive_path):
    """Restores database and media files from backup after verification."""
    print_banner()
    
    if not os.path.exists(archive_path):
        print(f"{RED}[Error] Backup archive file '{archive_path}' not found!{NC}")
        return False
        
    hash_file_path = archive_path + ".sha256"
    if not os.path.exists(hash_file_path):
        print(f"{RED}[Error] SHA-256 signature file '{hash_file_path}' not found!{NC}")
        print(f"{RED}[Error] Cannot verify backup integrity. Restore aborted for safety.{NC}")
        return False
        
    print(f"{GREEN}[*] Verifying backup integrity hash...{NC}")
    with open(hash_file_path, "r") as hf:
        expected_hash = hf.read().strip()
        
    actual_hash = compute_sha256(archive_path)
    if actual_hash != expected_hash:
        print(f"{RED}[CAUTION] CRITICAL SECURITY WARNING: Backup file hash mismatch!{NC}")
        print(f"          Expected: {expected_hash}")
        print(f"          Actual:   {actual_hash}")
        print(f"{RED}[Error] Backup file is corrupted or has been tampered with! Restore aborted.{NC}")
        return False
        
    print(f"{GREEN}[+] Integrity hash verified successfully!{NC}")
    
    # Confirm with user
    print(f"{YELLOW}[!] WARNING: Restoring will overwrite current database and media files.{NC}")
    confirm = input("Are you sure you want to proceed? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print(f"{YELLOW}Restore cancelled by user.{NC}")
        return False
        
    # Temporary backup directory for safety
    restore_temp = "restore_temp_safety"
    os.makedirs(restore_temp, exist_ok=True)
    
    # Backup existing files to restore_temp in case extraction fails
    temp_db_backed = False
    temp_media_backed = False
    
    try:
        if os.path.exists(DB_FILE):
            shutil.move(DB_FILE, os.path.join(restore_temp, DB_FILE))
            temp_db_backed = True
        if os.path.exists(MEDIA_DIR):
            shutil.move(MEDIA_DIR, os.path.join(restore_temp, MEDIA_DIR))
            temp_media_backed = True
            
        print(f"{GREEN}[*] Extracting database and media files...{NC}")
        with zipfile.ZipFile(archive_path, 'r') as zipf:
            zipf.extractall(".")
            
        # Clean up temporary safety backup
        shutil.rmtree(restore_temp, ignore_errors=True)
        print(f"{GREEN}[+] Restore completed successfully!{NC}")
        print(f"{GREEN}[+] System has been restored to backup timestamp state.{NC}")
        print(f"{BLUE}===================================================={NC}")
        return True
    except Exception as e:
        print(f"{RED}[Error] Extraction failed during restore: {e}{NC}")
        print(f"{YELLOW}[*] Attempting to roll back to pre-restore state...{NC}")
        # Rollback
        try:
            if temp_db_backed:
                if os.path.exists(DB_FILE):
                    os.remove(DB_FILE)
                shutil.move(os.path.join(restore_temp, DB_FILE), DB_FILE)
            if temp_media_backed:
                if os.path.exists(MEDIA_DIR):
                    shutil.rmtree(MEDIA_DIR, ignore_errors=True)
                shutil.move(os.path.join(restore_temp, MEDIA_DIR), MEDIA_DIR)
            print(f"{GREEN}[+] Rollback successful. System restored to pre-restore state.{NC}")
        except Exception as rollback_err:
            print(f"{RED}[Critical Error] Rollback failed! Pre-restore files are located in '{restore_temp}': {rollback_err}{NC}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Secure cross-platform Backup and Restore utility for IIA Management System.")
    subparsers = parser.add_subparsers(dest="command")
    
    # Backup parser
    subparsers.add_parser("backup", help="Run a secure transactional backup.")
    
    # Restore parser
    restore_parser = subparsers.add_parser("restore", help="Restore system from a verified backup.")
    restore_parser.add_argument("archive", type=str, help="Path to the backup .zip file.")
    
    args = parser.parse_args()
    
    if args.command == "backup":
        run_backup()
    elif args.command == "restore":
        run_restore(args.archive)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
