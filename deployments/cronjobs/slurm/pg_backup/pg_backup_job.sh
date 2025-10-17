#!/bin/bash
#SBATCH --time=2:00:00
#SBATCH --mem=4G
#SBATCH --partition=datamover
#SBATCH --job-name=pg_k8s_backup
#SBATCH --mail-type=FAIL,END

# --- Config ---
export KUBECONFIG=/path/to/your/kubeconfig  # Adjust this path
NAMESPACE="bgc-data-portal-hl-prod"
DUMP_POD="pg-lsn-check"
LAST_LSN_FILE="/path/to/ftp/data/db_backups/last_lsn.txt"
BACKUP_DIR="/path/to/ftp/data/db_backups"
FILENAME="db-$(date +%F).dump"
TMPFILE="/tmp/$FILENAME"
SYMLINK="$BACKUP_DIR/current.dump"

echo "[INFO] Starting backup job at $(date)"

# 1. Check current WAL LSN
CURRENT_LSN=$(kubectl run $DUMP_POD \
  -n $NAMESPACE \
  --rm -i --restart=Never \
  --image=postgres:15 \
  --env="PGPASSWORD=$POSTGRES_PASSWORD" \
  --command -- \
  psql -h postgres -U postgres -d bgc -Atc "SELECT pg_current_wal_lsn();" \
)

echo "[INFO] Current WAL LSN: $CURRENT_LSN"

# 2. Compare with last
if [[ -f "$LAST_LSN_FILE" ]]; then
  LAST_LSN=$(cat "$LAST_LSN_FILE")
  echo "[INFO] Last WAL LSN: $LAST_LSN"

  if [[ "$CURRENT_LSN" == "$LAST_LSN" ]]; then
    echo "[SKIP] No changes detected. Skipping dump."
    exit 0
  fi
fi

# 3. Dump the DB using pg_dump in a temporary pod
kubectl run pg-dump \
  --namespace $NAMESPACE \
  --image=postgres:15 \
  --restart=Never \
  --env="PGPASSWORD=$POSTGRES_PASSWORD" \
  --command -- \
  pg_dump -h postgres -U postgres -d bgc -F c \
  > "$TMPFILE"

# 4. Save dump and update metadata
cp "$TMPFILE" "$BACKUP_DIR/$FILENAME"
echo "$CURRENT_LSN" > "$LAST_LSN_FILE"
ln -sf "$BACKUP_DIR/$FILENAME" "$SYMLINK"

echo "[SUCCESS] Backup completed: $FILENAME"
