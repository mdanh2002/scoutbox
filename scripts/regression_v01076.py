from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT/path).read_text()

def fail(msg):
    raise SystemExit(f'FAIL: {msg}')

if read(Path('VERSION')).strip()!='0.10.76': fail('VERSION is not 0.10.76')
if read(Path('RELEASE_ID')).strip()!='ScoutBox v0.10.76': fail('RELEASE_ID stale')
if read(Path('BUILD_INFO.txt')).strip()!='ScoutBox v0.10.76': fail('BUILD_INFO stale')
if not read(Path('README.md')).startswith('# ScoutBox 0.10.76'): fail('README not bumped')
if not (ROOT/'docs'/'RELEASE_NOTES_0.10.76.md').is_file(): fail('0.10.76 release notes missing')

views=read(Path('portal/views.py'))
contacts=read(Path('templates/portal/contacts.html'))
sources=read(Path('templates/portal/sources.html'))
telemetry=read(Path('templates/portal/telemetry.html'))
css=read(Path('portal/static/portal/app.css'))

if 'contact_read_filter_counts' not in views or 'read_state' not in contacts or 'contact-read-filter' not in contacts:
    fail('Address Book Seen/New filter missing')
if 'country_total=country_count_base.distinct().count()' not in views:
    fail('Opportunity all-country total still excludes blank/current rows')
if 'campaign_total=campaign_count_base.distinct().count()' not in views:
    fail('Opportunity all-campaign total still excludes unassigned rows')
if 'campaign_counts={}' not in views or 'Q(origin_campaign_id=int(campaign))|Q(campaigns__pk=int(campaign))' not in views:
    fail('Campaign filter/counts do not include both origin and seen campaigns')
if 'country_total=_hidden_lead_visible_count(country_count_base)' not in views:
    fail('Hidden Lead country total not based on visible de-duplicated count')
if 'forum-source-name' not in sources or sources.find('forum-source-name') > sources.find('forum-source-health'):
    fail('Forum health icon is still before the forum name')
if 'provider_performance_legend' not in telemetry or 'token_model_legend' not in telemetry:
    fail('Telemetry legend export links missing')
if 'provider_performance_legend' not in views or 'token_model_legend' not in views:
    fail('Telemetry legend export handlers missing')
if 'discovery-performance-copy' not in css or 'max-height:315px' not in css:
    fail('Discovery Performance legend scrollbar missing')
if "Outer: input · middle: output · inner: reasoning." not in telemetry:
    fail('Token Usage help text was not updated to three rings')
if "ring('tokens'," in telemetry or "totalInner" in telemetry:
    fail('Token Usage chart still draws redundant total ring')
if 'kind+\' tokens: \'+current' not in telemetry or "if(hit.kind!=='output')" not in telemetry:
    fail('Token Usage tooltip does not avoid repeated selected token type')
print('ScoutBox 0.10.76 targeted regressions passed.')
