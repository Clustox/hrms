#!bin/bash

# /opt/hrms-src is a host bind-mount (root:hrms-owned) into this container
# (uid 1000). Git refuses to operate on a repo it does not own ("dubious
# ownership") unless told to trust it -- needed before any git operation
# touches it, including bench get-app's own internal git calls, or those
# fail (silently continuing past, since this script has no set -e) and
# leave hrms partially/incorrectly registered.
git config --global --add safe.directory /opt/hrms-src

if [ -d "/home/frappe/frappe-bench/apps/frappe" ]; then
    echo "Bench already exists, skipping init"
    cd frappe-bench
    # Make apps/hrms point at the mounted Clustox checkout, not whatever
    # was here before (a stale get-app clone, or nothing yet). Safe to
    # redo on every start -- it's a symlink swap, not a rebuild.
    rm -rf apps/hrms
    ln -sfn /opt/hrms-src apps/hrms
    # Bind dev server to all interfaces so Docker's published port is reachable
    sed -i 's|^web:.*bench serve.*|web: bench serve --port 8000 --host 0.0.0.0|' ./Procfile
    exec bench start
else
    echo "Creating new bench..."
fi

export PATH="${NVM_DIR}/versions/node/v${NODE_VERSION_DEVELOP}/bin/:${PATH}"

bench init --skip-redis-config-generation frappe-bench

cd frappe-bench

# Use containers instead of localhost
bench set-mariadb-host mariadb
bench set-redis-cache-host redis://redis:6379
bench set-redis-queue-host redis://redis:6379
bench set-redis-socketio-host redis://redis:6379

# Remove redis, watch from Procfile
sed -i '/redis/d' ./Procfile
sed -i '/watch/d' ./Procfile

bench get-app erpnext
# hrms comes from the Clustox repo mounted at /opt/hrms-src, not upstream
# frappe/hrms -- bare `bench get-app hrms` resolves through Frappe's app
# registry to plain upstream and has nothing to do with this fork.
# --soft-link makes apps/hrms a symlink to the mount instead of cloning,
# same end state as the "bench already exists" branch above. Verified in
# a disposable sandbox on this host -- see docs/runbook.md 2026-09-22.
bench get-app hrms /opt/hrms-src --soft-link
bench get-app telephony
bench get-app helpdesk

bench new-site hrms.localhost \
--force \
--mariadb-root-password 123 \
--admin-password admin \
--no-mariadb-socket

bench --site hrms.localhost install-app hrms
# helpdesk requires telephony; bench installs it automatically as a dependency
bench --site hrms.localhost install-app helpdesk
bench --site hrms.localhost set-config developer_mode 1
bench --site hrms.localhost enable-scheduler
bench --site hrms.localhost clear-cache
bench use hrms.localhost

# Bind dev server to all interfaces so Docker's published port is reachable.
# Re-applied here (not just above) because bench/get-app/new-site regenerate
# the Procfile along the way, silently dropping an earlier edit.
sed -i 's|^web:.*bench serve.*|web: bench serve --port 8000 --host 0.0.0.0|' ./Procfile

bench start
