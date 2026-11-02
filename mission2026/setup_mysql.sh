#!/bin/bash
# Mission 2026 — MySQL reset & app user creation
# Runs as root (via pkexec). Resets root password, creates app user + DB.
set -x

ROOT_PW='R00t_Mission_2026!'
APP_USER='mission'
APP_PW='M1ssion_2026_App!'
DB_NAME='mission2026'

MYSQLD=/usr/sbin/mysqld
MYSQL=/usr/bin/mysql
MYSQLADMIN=/usr/bin/mysqladmin

# 1. stop system mysql
/usr/bin/systemctl stop mysql
sleep 2

# 1b. systemd removes RuntimeDirectory on stop — recreate it for the temp server
mkdir -p /var/run/mysqld
chown mysql:mysql /var/run/mysqld
chmod 755 /var/run/mysqld

# 2. start temporary server without grant tables (socket only, no network)
rm -f /tmp/mysql_reset_err.log
"$MYSQLD" --skip-grant-tables --skip-networking --user=mysql \
  --log-error=/tmp/mysql_reset_err.log --daemonize >>/var/log/mysql_reset.log 2>&1
chmod 644 /tmp/mysql_reset_err.log 2>/dev/null

# wait for socket (up to 25s)
for i in $(seq 1 25); do
  if [ -S /var/run/mysqld/mysqld.sock ]; then break; fi
  sleep 1
done
chmod 666 /var/run/mysqld/mysqld.sock 2>/dev/null || true

# 3. reset credentials
"$MYSQL" -u root <<SQL
FLUSH PRIVILEGES;
ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '${ROOT_PW}';
CREATE USER IF NOT EXISTS '${APP_USER}'@'localhost' IDENTIFIED WITH mysql_native_password BY '${APP_PW}';
CREATE USER IF NOT EXISTS '${APP_USER}'@'127.0.0.1' IDENTIFIED WITH mysql_native_password BY '${APP_PW}';
CREATE DATABASE IF NOT EXISTS ${DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON ${DB_NAME}.* TO '${APP_USER}'@'localhost';
GRANT ALL PRIVILEGES ON ${DB_NAME}.* TO '${APP_USER}'@'127.0.0.1';
FLUSH PRIVILEGES;
SQL
RC=$?

# 4. shut down temp server & restart normal one
"$MYSQLADMIN" -u root -p"${ROOT_PW}" shutdown 2>/dev/null || /usr/bin/pkill -f skip-grant-tables
sleep 3
/usr/bin/systemctl start mysql
sleep 4
/usr/bin/systemctl is-active mysql

# 5. verify app user works
"$MYSQL" -u "$APP_USER" -p"${APP_PW}" -e "SELECT 'APP_USER_OK';" ${DB_NAME} 2>/dev/null

echo "SCRIPT_RC=$RC"
exit $RC
