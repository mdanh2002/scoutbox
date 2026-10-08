from pathlib import Path
root = Path(__file__).resolve().parents[1]
contacts = (root/'templates/portal/contacts.html').read_text()
required = [
    'function showContactFilterProgress',
    'function contactFilterSummary',
    'function manualFilterStrongFitCount',
    "showContactFilterProgress(jobId,manualFilterLiveMessage(d),d.finished?100:(d.progress||0))",
    "showContactFilterProgress(d.job_id,d.message||'Queued',0)",
]
missing = [x for x in required if x not in contacts]
if missing:
    raise SystemExit('0.11.7 Address Book re-evaluation regression failed: missing '+', '.join(missing))
if contacts.count('function showContactFilterProgress') != 1:
    raise SystemExit('0.11.7 Address Book re-evaluation regression failed: duplicate/missing showContactFilterProgress')
print('0.11.7 Address Book re-evaluation progress regression passed')
