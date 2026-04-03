#!/bin/bash
# backup.sh — Back up the On The Boat Charters database
# Usage: ./backup.sh
# Recommended: run via cron daily, e.g.
#   0 3 * * * cd /path/to/ontheboat && ./backup.sh

BACKUP_DIR="./backups"
DB_FILE="ontheboat.db"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/ontheboat_${TIMESTAMP}.db"

mkdir -p "$BACKUP_DIR"

if [ -f "$DB_FILE" ]; then
    # Use SQLite's .backup command for a safe hot copy
    sqlite3 "$DB_FILE" ".backup '${BACKUP_FILE}'"
    echo "✓ Backup created: ${BACKUP_FILE}"
    
    # Keep only the last 30 backups
    ls -1t "${BACKUP_DIR}"/ontheboat_*.db 2>/dev/null | tail -n +31 | xargs -r rm
    echo "✓ Old backups cleaned (keeping last 30)"
else
    echo "✗ Database file not found: ${DB_FILE}"
    exit 1
fi
