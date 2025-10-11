#!/bin/bash
# Script to restore credentials.json from backup

BACKUP_PATH=~/credentials.json.backup
TARGET_PATH="$(dirname "$0")/credentials.json"

if [ -f "$BACKUP_PATH" ]; then
    cp "$BACKUP_PATH" "$TARGET_PATH"
    echo "✅ Credentials restored from backup"
else
    echo "❌ No backup found at $BACKUP_PATH"
    echo "Please place your credentials.json file manually"
fi
