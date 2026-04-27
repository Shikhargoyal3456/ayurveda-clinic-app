#!/bin/bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p "$BACKUP_DIR"

docker compose exec -T db pg_dump -U postgres ayurveda > "$BACKUP_DIR/db_$DATE.sql"

if [ -d uploads ]; then
  tar -czf "$BACKUP_DIR/uploads_$DATE.tar.gz" uploads/
fi

if [ -n "${AWS_BACKUP_BUCKET:-}" ]; then
  aws s3 cp "$BACKUP_DIR/db_$DATE.sql" "s3://$AWS_BACKUP_BUCKET/db_$DATE.sql"
  if [ -f "$BACKUP_DIR/uploads_$DATE.tar.gz" ]; then
    aws s3 cp "$BACKUP_DIR/uploads_$DATE.tar.gz" "s3://$AWS_BACKUP_BUCKET/uploads_$DATE.tar.gz"
  fi
fi

find "$BACKUP_DIR" -type f -mtime +30 -delete

echo "Backup complete: $DATE"
