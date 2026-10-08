from pathlib import Path
root=Path(__file__).resolve().parents[1]
def read(p): return (root/p).read_text()
assert read('VERSION').strip()=='0.11.71'
assert 'stats_service:' in read('docker-compose.yml')
assert './.scoutbox-runtime:/config:ro' in read('docker-compose.yml')
assert 'ports:' not in read('docker-compose.yml').split('  stats_service:',1)[1].split('  web:',1)[0]
assert 'External Statistics' in read('templates/portal/_system_tabs.html')
assert 'ToughDev Stats' not in read('templates/portal/_system_tabs.html')
assert 'External statistics unavailable.' in read('templates/portal/settings.html')
assert 'migrate_external_stats_config' in read('entrypoint.sh')
assert 'pymysql.connect' not in read('portal/services/blogstats.py')
assert 'http://stats_service:8787' in read('portal/services/blogstats.py')
assert (root/'stats_service/server.py').exists()
print('ScoutBox 0.11.71 regression checks passed')
