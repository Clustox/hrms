#!bin/bash

if [ -d "/home/frappe/frappe-bench/apps/frappe" ]; then
    echo "Bench already exists, skipping init"
    cd frappe-bench
    # Bind dev server to all interfaces so Docker's published port is reachable
    sed -i 's|^web:.*bench serve.*|web: bench serve --port 8000 --host 0.0.0.0|' ./Procfile
    bench start
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
bench get-app hrms

bench new-site hrms.localhost \
--force \
--mariadb-root-password 123 \
--admin-password admin \
--no-mariadb-socket

bench --site hrms.localhost install-app hrms
bench --site hrms.localhost set-config developer_mode 1
bench --site hrms.localhost enable-scheduler
bench --site hrms.localhost clear-cache
bench use hrms.localhost

# Bind dev server to all interfaces so Docker's published port is reachable.
# Re-applied here (not just above) because bench/get-app/new-site regenerate
# the Procfile along the way, silently dropping an earlier edit.
sed -i 's|^web:.*bench serve.*|web: bench serve --port 8000 --host 0.0.0.0|' ./Procfile

bench start