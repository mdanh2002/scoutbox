-- ScoutBox: minimum read-only grants for tracking-link attribution.
-- Replace toughdev_stats and the password. Run as a MySQL/MariaDB administrator.

CREATE USER IF NOT EXISTS 'opportal_ro'@'%' IDENTIFIED BY 'CHANGE-TO-A-LONG-RANDOM-PASSWORD';
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'opportal_ro'@'%';
GRANT SELECT ON toughdev_stats.pageviews TO 'opportal_ro'@'%';
GRANT SELECT ON toughdev_stats.request_logs TO 'opportal_ro'@'%';
FLUSH PRIVILEGES;

-- Verification as opportal_ro:
-- SELECT item_id,page_id,view_count,last_accessed FROM toughdev_stats.pageviews ORDER BY item_id DESC LIMIT 5;
-- SELECT id,request_uri,created_at FROM toughdev_stats.request_logs ORDER BY id DESC LIMIT 5;
-- Any INSERT/UPDATE/DELETE/DDL should fail.
