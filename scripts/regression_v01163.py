from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
read=lambda p:(ROOT/p).read_text()
assert read('VERSION').strip()=='0.11.63'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.63'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.63'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.63'
assert (ROOT/'docs'/'RELEASE_NOTES_0.11.63.md').exists()
views=read('portal/views.py')
stats=read('templates/portal/stats.html')
contacts=read('templates/portal/contacts.html')
blacklist=read('templates/portal/blacklist.html')
css=read('portal/static/portal/app.css')
assert "point['items']=[item]" in views
assert "record_item={'label':title,'date':_stats_map_date" in views
assert "reverse('contacts')+'?edit='" in views
assert "reverse('blacklist')+'?edit='" in views
assert "map_edit_contact=" in views and "map_edit_blacklist=" in views
assert 'pointItems(point)' in stats and 'items.slice(0,5)' in stats
assert "more record" in stats and 'stats-map-record-popover' in stats
assert "Status" not in stats[stats.find('function pointTip'):stats.find('function closeMapRecordPopover')]
assert 'map_edit_contact' in contacts and 'map_edit_blacklist' in blacklist
assert '.stats-map-record-popover{' in css
print('ScoutBox 0.11.63 regression checks passed')
