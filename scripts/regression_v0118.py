from pathlib import Path
root=Path(__file__).resolve().parents[1]
cold=(root/'portal/services/cold.py').read_text()
discovery=(root/'portal/services/discovery.py').read_text()
cloud=(root/'portal/services/cloud_discovery.py').read_text()
required=[
    'hidden_lead_minibrowser_collect',
    'hidden_lead_minibrowser_admission',
    '_LEAD_MINIBROWSER_ADMIT_CUTOFF=75',
    'Topical relevance alone is not enough',
    'Favor small specialist companies',
    'decision (admit/review/reject)',
]
missing=[x for x in required if x not in cold]
if missing:
    raise SystemExit('0.11.8 Hidden Lead minibrowser gate regression failed: missing '+', '.join(missing))
if 'hidden_lead_minibrowser_admission(' not in discovery or 'Hidden-Leads only' not in discovery:
    raise SystemExit('0.11.8 regression failed: source-guided Hidden Lead path is not gated')
if 'hidden_lead_minibrowser_admission(' not in cloud or 'Hidden Leads only' not in cloud:
    raise SystemExit('0.11.8 regression failed: cloud Hidden Lead path is not gated')
if 'persist_cloud_contacts' in cold:
    raise SystemExit('0.11.8 regression failed: gate leaked into Address Book implementation')
print('0.11.8 Hidden Leads minibrowser admission regression passed')
