# Secure Backup & Restore Guide

This guide provides instructions on how to manage and automate secure backups for the IIA Observatory Operations & Management System. The backup utility secures all database records (including PM, Inventory, TCS, chat messages, logs, settings) and all media uploads, verifying file integrity to protect against data loss.

The system supports both **Web UI-based Export/Import** for Root Super Admins and **CLI/Automation scripts** for Linux/AWS EC2 and Windows deployments.

---

## 1. Web UI Backup & Restore (Root Super Admin)

Super Admins (`ROOT`) can create downloadable backups or restore state directly from the system settings interface:

1. Log in as a **Root Administrator / Superuser**.
2. Navigate to **Settings** (`/accounts/settings/#system`).
3. Under **System Administration**, locate the **System Disaster Recovery & Backup Engine** section.
4. **Export Backup**:
   - Check the management modules to include (`[x] Project Management`, `[x] Inventory Management`, `[x] Telescope Control System`, `[x] Media Files`, `[x] Database Dump`).
   - Click **Export Complete Backup Archive (.zip)** to download a complete timestamped `.zip` archive.
5. **Import & Restore Backup**:
   - Upload any previously generated `.zip` backup file.
   - Click **Restore System State From Backup** to safely restore all database records and media files with zero data loss.

---

## 2. CLI Quick Commands Overview

The cross-platform backup script [backup_restore.py](file:///d:/ubuntu%20file/IIAP%20PM%20and%20IM/backup_restore.py) is located in the project root directory.

### Create a Backup:
```bash
pmimvenv/Scripts/python backup_restore.py backup
```
- Creates a secure `.zip` file inside a `backups/` directory containing the database and the `media/` folder.
- Automatically generates a `.sha256` signature file containing the cryptographic checksum.
- Keeps only the last 10 backups and deletes older files to save disk space.

### Restore a Backup:
```bash
pmimvenv/Scripts/python backup_restore.py restore backups/backup_YYYYMMDD_HHMMSS.zip
```
- Recalculates the archive's SHA-256 checksum and compares it against the `.sha256` file to verify integrity.
- Prompts for confirmation before overwriting active database or media uploads.
- Automatically rolls back to the previous active state if extraction fails.

---

## 3. Automating Nightly Backups (Linux / AWS EC2 & Windows)

### Option A: Linux / AWS EC2 (cron)

To schedule automated nightly backups on an AWS EC2 instance or Linux server:

1. Open crontab editor:
   ```bash
   crontab -e
   ```
2. Add the following cron rule to execute every night at 11:59 PM:
   ```cron
   59 23 * * * cd "/d/ubuntu file/IIAP PM and IM" && pmimvenv/bin/python backup_restore.py backup >> backups/backup_cron.log 2>&1
   ```

### Option B: Windows (Task Scheduler)

1. Open **Task Scheduler**.
2. Create a daily task scheduled for `11:59:00 PM`.
3. Action: **Start a program**.
4. Program/script: `D:\ubuntu file\IIAP PM and IM\pmimvenv\Scripts\python.exe`
5. Arguments: `backup_restore.py backup`
6. Start in: `D:\ubuntu file\IIAP PM and IM`

---

## 4. Data Integrity & Recovery Guarantee

### SHA-256 Signature Verification
Every backup generates a signature file (`backup_YYYYMMDD_HHMMSS.zip.sha256`). Before a restore operation is executed, the checksum is verified to ensure zero data corruption or tampering.

### Safety Rollbacks
In the event that a restore extraction fails midway, the system automatically rolls back, recovering the pre-restore database and media folders without data loss.
