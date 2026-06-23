# Secure Backup & Restore Guide

This guide provides instructions on how to manually manage and automate secure backups for the IIA Management System. The backup utility secures all database records (including chat messages, logs, settings) and all media uploads, verifying file integrity with SHA-256 signatures to protect against tampering or corruption.

The tool uses Python, making it fully cross-platform and compatible with both **Windows** and **Linux/Ubuntu**.

---

## 1. Quick Commands Overview

The backup script [backup_restore.py](file:///d:/Saran%20Projects/IIA%20Management-own/backup_restore.py) is located in the project root directory.

### Create a Backup:
```bash
.venv_win/Scripts/python backup_restore.py backup
```
- Creates a secure `.zip` file inside a `backups/` directory containing the database and the `media/` folder.
- Automatically generates a `.sha256` signature file containing the cryptographic checksum.
- Keeps only the last 10 backups and deletes older files to save disk space.

### Restore a Backup:
```bash
.venv_win/Scripts/python backup_restore.py restore backups/backup_YYYYMMDD_HHMMSS.zip
```
- Recalculates the archive's SHA-256 checksum and compares it against the `.sha256` file to verify integrity.
- Prompts for confirmation before overwriting active database or media uploads.
- Automatically rolls back to the previous active state if extraction fails.

---

## 2. Automating Backups Daily at 11:59 PM

### Option A: Windows (Task Scheduler)

To configure the backup script to run every night at 11:59 PM on Windows:

1. Open the **Start Menu**, search for **Task Scheduler**, and run it.
2. In the right-hand **Actions** panel, click **Create Basic Task...**
3. **Name**: `IIA Nightly Backup`
4. **Trigger**: Select **Daily** and click Next.
5. **Start time**: Set the time to `11:59:00 PM` and set it to recur every `1` day. Click Next.
6. **Action**: Select **Start a program** and click Next.
7. **Program/script**: Enter the path to the Python executable in your virtual environment:
   `D:\Saran Projects\IIA Management-own\.venv_win\Scripts\python.exe`
8. **Add arguments**: Enter the script name and command:
   `backup_restore.py backup`
9. **Start in**: Enter the absolute path to your project root folder:
   `D:\Saran Projects\IIA Management-own`
10. Click **Next** and then **Finish**.

> [!NOTE]
> Ensure that the user account running the task has write permissions to the project directory.

---

### Option B: Linux / Ubuntu (cron)

To schedule backups on a Linux server using `cron`:

1. Open your terminal and edit the cron configuration for the current user:
   ```bash
   crontab -e
   ```
2. Append the following cron job rule at the bottom of the file:
   ```cron
   59 23 * * * cd "/d/Saran Projects/IIA Management-own" && .venv_win/bin/python backup_restore.py backup >> backups/backup_cron.log 2>&1
   ```
3. Save and close the editor.

**Explanation of the Cron Schedule (`59 23 * * *`)**:
* `59` : Minute (59th minute)
* `23` : Hour (23rd hour, representing 11:00 PM)
* `* * *` : Every day of the month, month, and day of the week.
* This executes the backup command exactly at **11:59 PM** every single night.

---

## 3. Data Integrity & Recovery Procedures

### SHA-256 Signature Verification
Every backup generates a parallel file (e.g., `backup_20260623_235900.zip.sha256`). This signature contains the SHA-256 hash of the archive.
Before a restore operation is executed, the script computes the SHA-256 checksum of the target archive and compares it with the saved signature. If they do not match, the restore is blocked.

### Safety Rollbacks
In the event that the restore extraction fails (e.g., due to a disk space exhaustion or permission error), the script automatically rolls back, recovering the pre-restore database and media folders from a temporary directory (`restore_temp_safety`), preventing any accidental data loss.
