#!/usr/bin/env bash
#
# Refresh the dev site from a fresh production backup, then anonymise it.
# Run on the host (user with docker access), e.g.:
#   bash /opt/app/hrms-dev/scripts/dev/refresh_dev.sh
#
# What it does:
#   1. Backs up the prod DB (read-only on prod).
#   2. Sets mute_emails=1 in the dev site_config (file; survives restore).
#   3. Restores the prod DB into the dev site (dev data is replaced).
#   4. Locks email on dev (disable all accounts + flush the queue).
#   5. Runs the anonymiser and prints a clean/leak verification.
#
# Email safety: mute_emails is set BEFORE the restore and the accounts are
# disabled immediately after, so a restored prod mailbox can never send.
set -euo pipefail

PROD=docker-frappe-1
DEV=dev-frappe-1
SITE=hrms.localhost
SELFDIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> 1/5  prod backup"
BK=$(sudo docker exec -i -w /home/frappe/frappe-bench "$PROD" bench --site "$SITE" backup \
       | awk '/Database/{print $2}')
echo "    $BK"

echo "==> 2/5  mute_emails on dev (file-based, survives restore)"
sudo docker exec -i -w /home/frappe/frappe-bench "$DEV" bench --site "$SITE" set-config mute_emails 1 >/dev/null

echo "==> 3/5  copy backup -> dev and restore"
sudo docker cp "$PROD:$BK" /tmp/_proddb.sql.gz
sudo docker cp /tmp/_proddb.sql.gz "$DEV:/tmp/_proddb.sql.gz"
sudo rm -f /tmp/_proddb.sql.gz
sudo docker exec -i -w /home/frappe/frappe-bench "$DEV" bench --site "$SITE" --force restore \
     /tmp/_proddb.sql.gz --mariadb-root-password 123
sudo docker exec -u root "$DEV" rm -f /tmp/_proddb.sql.gz

echo "==> 4/5  lock email on dev"
sudo docker exec -i -w /home/frappe/frappe-bench "$DEV" bench --site "$SITE" execute frappe.db.sql \
     --kwargs "{'query': \"UPDATE \`tabEmail Account\` SET enable_outgoing=0, enable_incoming=0, default_outgoing=0\"}" >/dev/null || true
sudo docker exec -i -w /home/frappe/frappe-bench "$DEV" bench --site "$SITE" execute frappe.db.sql \
     --kwargs "{'query': 'DELETE FROM \`tabEmail Queue\`'}" >/dev/null || true

echo "==> 5/5  anonymise + verify"
sudo docker cp "$SELFDIR/anonymize_dev.py" "$DEV:/home/frappe/frappe-bench/apps/hrms/hrms/anonymize_dev.py"
sudo docker exec -u root "$DEV" chown frappe:frappe /home/frappe/frappe-bench/apps/hrms/hrms/anonymize_dev.py
sudo docker exec -i -w /home/frappe/frappe-bench "$DEV" bench --site "$SITE" execute hrms.anonymize_dev.run
sudo docker exec -u root "$DEV" rm -f /home/frappe/frappe-bench/apps/hrms/hrms/anonymize_dev.py

echo "==> done. ANON line above: clean=true means zero real emails/domains remain."
