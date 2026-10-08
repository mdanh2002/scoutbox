"""Historical application import with AI-first layout inference.

The importer intentionally does not require a spreadsheet schema. DOCX/PDF/TXT/CSV/XLSX
are converted into compact evidence chunks, then the configured AI route for
``import_inference`` interprets the layout/content. Missing values stay blank. A
conservative deterministic parser is retained only as an offline fallback.
"""
import csv
import io
import json
import re
from datetime import datetime
from django.utils import timezone
from portal.models import ImportCandidate, Opportunity, Application
from .ai import generate, route_for_stage

ALLOWED_STATUSES={'applied','reply','interview','rejected','accepted','closed'}
HEADER_MAP={
    'company':'company','employer':'company','organisation':'company','organization':'company','client':'company',
    'role':'role_title','job':'role_title','job title':'role_title','title':'role_title','position':'role_title',
    'url':'url','link':'url','job url':'url','posting':'url',
    'email':'email','contact email':'email','contact':'email',
    'date':'date_applied','date applied':'date_applied','applied date':'date_applied','application date':'date_applied',
    'channel':'channel','type':'channel','application type':'channel',
    'status':'outcome_status','outcome':'outcome_status','result':'outcome_status',
    'notes':'notes','note':'notes','comments':'notes','comment':'notes','details':'notes','reason':'notes',
}
STATUS_ALIASES={
    'applied':'applied','sent':'applied','submitted':'applied','application sent':'applied',
    'reply':'reply','replied':'reply','response':'reply','responded':'reply',
    'interview':'interview','interviewing':'interview','progressing':'interview','in progress':'interview',
    'rejected':'rejected','reject':'rejected','declined':'rejected','unsuccessful':'rejected','not a match':'rejected','no match':'rejected','not suitable':'rejected',
    'accepted':'accepted','offer':'accepted','hired':'accepted','engaged':'accepted',
    'closed':'closed','withdrawn':'closed','not proceeding':'closed',
}


def _clean(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def _parse_date(value):
    value=_clean(value)
    if not value:
        return None
    # Only parse dates that are explicit enough to identify a day. Partial month/year
    # values remain blank rather than being silently converted to an invented date.
    for fmt in ('%Y-%m-%d','%Y-%m-%d %H:%M:%S','%d/%m/%Y','%d/%m/%Y %H:%M','%m/%d/%Y','%Y/%m/%d','%d %b %Y','%b %d %Y','%d %B %Y','%B %d %Y'):
        try:
            return timezone.make_aware(datetime.strptime(value,fmt))
        except Exception:
            pass
    return None


def _status(value):
    value=_clean(value).lower()
    if not value:
        return ''
    return STATUS_ALIASES.get(value, value if value in ALLOWED_STATUSES else '')


def _normalise_company(value):
    value=_clean(value).lower()
    value=re.sub(r'\b(pte\.?\s*ltd\.?|private limited|limited|ltd\.?|inc\.?|incorporated|llc|l\.l\.c\.|corp\.?|corporation|gmbh|plc|company|co\.?)\b',' ',value)
    return re.sub(r'[^a-z0-9]+',' ',value).strip()


def _create_candidate(data, source, raw='', method='heuristic', metadata=None):
    """Create a proposal without filling absent fields with guesses."""
    company=_clean(data.get('company',''))
    role=_clean(data.get('role_title',''))
    url=_clean(data.get('url',''))
    email=_clean(data.get('email',''))
    channel=_clean(data.get('channel',''))
    notes=_clean(data.get('notes',''))
    status=_status(data.get('outcome_status',''))
    if url and not re.match(r'^https?://',url,re.I):
        url=''
    if email and '@' not in email:
        email=''
    if not any([company,role,url,email,notes]):
        return None
    confidence=data.get('confidence',0)
    try: confidence=max(0,min(100,int(float(confidence))))
    except Exception: confidence=0
    # Company is the primary historical duplicate anchor. A proposal without it is
    # still reviewable but cannot be treated as high confidence.
    if company:
        confidence=max(confidence,75 if role else 60)
    else:
        confidence=min(confidence or 30,35)
    return ImportCandidate.objects.create(
        source=source, company=company[:220], role_title=role[:300], url=url[:1000], email=email[:254],
        date_applied=_parse_date(data.get('date_applied','')), channel=channel[:30], outcome_status=status,
        notes=notes[:10000], confidence=confidence,
        raw_excerpt=(raw or _clean(data.get('evidence','')))[:4000],
        inference_method=method[:40], inference_metadata=metadata or {},
    )


def _header_key(value):
    key=_clean(value).lower().strip(' :_-')
    direct=HEADER_MAP.get(key)
    if direct:return direct
    compact=re.sub(r'[^a-z0-9]+',' ',key).strip()
    if ('date' in compact or 'when' in compact) and any(x in compact for x in ('appl','submit','sent','date','when')): return 'date_applied'
    if any(x in compact for x in ('channel','application method','application source','source type','how applied','via')): return 'channel'
    if any(x in compact for x in ('company','employer','organisation','organization','client')): return 'company'
    if any(x in compact for x in ('role','job title','position','vacancy title')): return 'role_title'
    if any(x in compact for x in ('url','link','posting','job page')): return 'url'
    if 'email' in compact: return 'email'
    if any(x in compact for x in ('status','outcome','result')): return 'outcome_status'
    if any(x in compact for x in ('note','comment','detail','reason')): return 'notes'
    return None


def _heuristic_table_rows(rows, source='document'):
    """Offline fallback. It may use recognizable labels but they are never required."""
    rows=[[_clean(v) for v in row] for row in rows if any(_clean(v) for v in row)]
    if not rows:
        return []
    mapped=[_header_key(v) for v in rows[0]]
    recognized=sum(1 for x in mapped if x)
    created=[]
    if recognized>=2 and ('company' in mapped or 'role_title' in mapped):
        for row in rows[1:]:
            data={}
            for idx,key in enumerate(mapped):
                if key and idx<len(row): data[key]=row[idx]
            c=_create_candidate(data,source,' | '.join(row),'heuristic-header',{'fallback':True})
            if c: created.append(c)
        return created
    return _heuristic_parse_text('\n'.join(' | '.join(row) for row in rows),source)


def _heuristic_parse_text(text, source='text'):
    created=[]
    # First attempt labelled blocks wherever they occur.
    blocks=re.split(r'\n\s*\n+',text or '')
    for block in blocks:
        fields={}; current=None
        for raw in block.splitlines():
            m=re.match(r'^\s*(company|employer|organisation|organization|role|job title|title|url|link|email|date applied|date|channel|status|outcome|notes?|comments?|details)\s*:\s*(.*)$',raw,re.I)
            if m:
                key=_header_key(m.group(1)); current=key
                if key: fields[key]=m.group(2).strip()
            elif current=='notes' and raw.strip():
                fields['notes']=(fields.get('notes','')+' '+raw.strip()).strip()
        if fields:
            c=_create_candidate(fields,source,block,'heuristic-labelled',{'fallback':True})
            if c: created.append(c)
    if created:
        return created

    # Last-resort row interpretation. This is intentionally low-confidence and exists
    # only so imports remain usable when no AI runtime is configured.
    for raw in (text or '').splitlines():
        line=raw.strip()
        if not line or line.startswith('#'): continue
        parts=[_clean(x) for x in re.split(r'\s*\|\s*|\t+',line)]
        if len(parts)<2:
            continue
        keys=['company','role_title','url','email','date_applied','channel','outcome_status']
        data={key:parts[i] for i,key in enumerate(keys) if i<len(parts)}
        if len(parts)>7: data['notes']=' | '.join(parts[7:])
        c=_create_candidate(data,source,line,'heuristic-row',{'fallback':True,'low_confidence':True})
        if c: created.append(c)
    return created


def _json_payload(text):
    """Extract JSON from models that may wrap it in markdown fences or prose."""
    value=(text or '').strip()
    value=re.sub(r'^```(?:json)?\s*','',value,flags=re.I)
    value=re.sub(r'\s*```$','',value)
    candidates=[value]
    start=value.find('{'); end=value.rfind('}')
    if start>=0 and end>start: candidates.append(value[start:end+1])
    start=value.find('['); end=value.rfind(']')
    if start>=0 and end>start: candidates.append(value[start:end+1])
    for candidate in candidates:
        try:
            data=json.loads(candidate)
            if isinstance(data,list): return {'records':data}
            if isinstance(data,dict): return data
        except Exception:
            continue
    raise RuntimeError('AI import inference did not return valid JSON')


def _ai_prompt(content, context='document'):
    return f'''You are interpreting historical job-application records from an arbitrary {context} layout.
The source may be a spreadsheet with unknown columns, a table, personal notes, copied emails, or prose. Infer structure from context rather than expecting column names.

CRITICAL RULES:
- Extract only genuine job/application records supported by the supplied content.
- COMPANY NAME is the most important duplicate anchor. Copy the actual employer/company when explicit. Do not invent one.
- Never fill a missing field from general knowledge, assumptions, a domain name, an ATS vendor, or a recruiter unless the content clearly identifies that value.
- Missing/uncertain fields MUST be an empty string, except date_applied may be null.
- A recruiter, job board, ATS, email provider, or search site is not the employer unless the source explicitly says so.
- Keep separate roles at the same company as separate records when the source clearly contains them.
- Put free-form comments, rejection reasons, interview details, follow-up context, and other useful historical information into notes.
- Normalize outcome_status only when explicit: applied, reply, interview, rejected, accepted, closed. Otherwise use an empty string.
- Normalize channel only when explicit enough (for example email, ats, website, public, community). Otherwise use an empty string.
- date_applied must be YYYY-MM-DD only when an exact date is explicit; otherwise null.
- confidence is 0-100 confidence in the interpretation, not in the candidate/job quality.
- evidence should quote/describe the smallest relevant source fragment, not invent facts.

Return ONLY JSON in this exact shape:
{{"records":[{{"company":"","role_title":"","url":"","email":"","date_applied":null,"channel":"","outcome_status":"","notes":"","confidence":0,"evidence":""}}]}}
Return an empty records array if this chunk contains no application history.

SOURCE CONTENT:
{content}
'''


def _infer_chunk(content, context='document'):
    route=route_for_stage('import_inference')
    if not route:
        raise RuntimeError('No AI provider configured for import inference')
    output=generate(_ai_prompt(content,context),stage='import_inference')
    payload=_json_payload(output)
    rows=payload.get('records') or []
    if not isinstance(rows,list):
        raise RuntimeError('AI import JSON records is not a list')
    cleaned=[]
    for row in rows[:200]:
        if not isinstance(row,dict): continue
        cleaned.append({
            'company':_clean(row.get('company','')),
            'role_title':_clean(row.get('role_title','')),
            'url':_clean(row.get('url','')),
            'email':_clean(row.get('email','')),
            'date_applied':row.get('date_applied') or '',
            'channel':_clean(row.get('channel','')),
            'outcome_status':_status(row.get('outcome_status','')),
            'notes':_clean(row.get('notes','')),
            'confidence':row.get('confidence',0),
            'evidence':_clean(row.get('evidence','')),
        })
    return cleaned, {'provider':route.get('provider',''),'model':route.get('model',''),'stage':'import_inference'}


def _dedupe_inferred(records):
    """Merge repeated AI records across chunks without merging different roles."""
    merged={}
    for item in records:
        company=_normalise_company(item.get('company',''))
        role=re.sub(r'[^a-z0-9]+',' ',_clean(item.get('role_title','')).lower()).strip()
        url=_clean(item.get('url','')).lower()
        email=_clean(item.get('email','')).lower()
        # Prefer company+role. URL/email only disambiguate records whose company/role is absent.
        key=(company,role) if company or role else ('',url or email or _clean(item.get('evidence',''))[:120].lower())
        if key not in merged:
            merged[key]=item.copy(); continue
        cur=merged[key]
        for field in ['company','role_title','url','email','date_applied','channel','outcome_status']:
            if not cur.get(field) and item.get(field): cur[field]=item[field]
        notes=[x for x in [cur.get('notes',''),item.get('notes','')] if x]
        cur['notes']=' | '.join(dict.fromkeys(notes))[:10000]
        evid=[x for x in [cur.get('evidence',''),item.get('evidence','')] if x]
        cur['evidence']=' | '.join(dict.fromkeys(evid))[:4000]
        try: cur['confidence']=max(int(cur.get('confidence') or 0),int(item.get('confidence') or 0))
        except Exception: pass
    return list(merged.values())


def _split_text(text, max_chars=26000):
    text=text or ''
    if len(text)<=max_chars: return [text]
    chunks=[]; current=[]; size=0
    for para in re.split(r'(\n\s*\n+)',text):
        if size+len(para)>max_chars and current:
            chunks.append(''.join(current)); current=[]; size=0
        if len(para)>max_chars:
            for i in range(0,len(para),max_chars):
                part=para[i:i+max_chars]
                if current: chunks.append(''.join(current)); current=[]; size=0
                chunks.append(part)
        else:
            current.append(para); size+=len(para)
    if current: chunks.append(''.join(current))
    return [x for x in chunks if x.strip()]


def _rows_to_chunks(rows, label='sheet', max_rows=40):
    compact=[]
    for idx,row in enumerate(rows,1):
        vals=[]
        for col,val in enumerate(row,1):
            text=_clean(val)[:1200]
            if text: vals.append(f'C{col}={json.dumps(text,ensure_ascii=False)}')
        if vals: compact.append(f'R{idx}: '+', '.join(vals))
    return [f'{label}\n'+'\n'.join(compact[i:i+max_rows]) for i in range(0,len(compact),max_rows)]


def _uploaded_chunks(upload):
    name=(upload.name or '').lower()
    if name.endswith('.docx'):
        from docx import Document
        doc=Document(upload); chunks=[]
        paragraph_text='\n'.join(p.text for p in doc.paragraphs if p.text.strip())
        chunks += _split_text('DOCX PARAGRAPHS\n'+paragraph_text) if paragraph_text.strip() else []
        for idx,table in enumerate(doc.tables,1):
            rows=[[c.text for c in row.cells] for row in table.rows]
            chunks += _rows_to_chunks(rows,f'DOCX TABLE {idx}')
        return chunks
    if name.endswith(('.xlsx','.xlsm')):
        from openpyxl import load_workbook
        wb=load_workbook(upload,read_only=True,data_only=True); chunks=[]
        for ws in wb.worksheets:
            chunks += _rows_to_chunks(list(ws.iter_rows(values_only=True)),f'WORKSHEET {json.dumps(ws.title)}')
        return chunks
    if name.endswith('.csv'):
        raw=upload.read().decode('utf-8-sig',errors='replace')
        try:
            dialect=csv.Sniffer().sniff(raw[:8192],delimiters=',;\t|')
            rows=list(csv.reader(io.StringIO(raw),dialect))
            return _rows_to_chunks(rows,'CSV ROWS')
        except Exception:
            return _split_text(raw)
    if name.endswith('.txt'):
        return _split_text(upload.read().decode('utf-8',errors='replace'))
    if name.endswith('.pdf'):
        from pypdf import PdfReader
        reader=PdfReader(upload); chunks=[]
        for idx,page in enumerate(reader.pages,1):
            text=page.extract_text() or ''
            chunks += _split_text(f'PDF PAGE {idx}\n{text}')
        return chunks
    raise RuntimeError('Supported imports: DOCX, PDF, XLSX, TXT, CSV')


def _fallback_for_upload(upload, source='document'):
    """Re-open-compatible deterministic fallback; caller passes a fresh in-memory copy."""
    name=(upload.name or '').lower()
    if name.endswith('.docx'):
        from docx import Document
        doc=Document(upload); created=[]
        for table in doc.tables:
            created.extend(_heuristic_table_rows([[c.text for c in row.cells] for row in table.rows],source))
        text='\n'.join(p.text for p in doc.paragraphs)
        if text.strip(): created.extend(_heuristic_parse_text(text,source))
        return created
    if name.endswith(('.xlsx','.xlsm')):
        from openpyxl import load_workbook
        wb=load_workbook(upload,read_only=True,data_only=True); created=[]
        for ws in wb.worksheets: created.extend(_heuristic_table_rows(list(ws.iter_rows(values_only=True)),source))
        return created
    if name.endswith('.csv'):
        raw=upload.read().decode('utf-8-sig',errors='replace')
        try:
            dialect=csv.Sniffer().sniff(raw[:4096],delimiters=',;\t|')
            return _heuristic_table_rows(list(csv.reader(io.StringIO(raw),dialect)),source)
        except Exception: return _heuristic_parse_text(raw,source)
    if name.endswith('.txt'): return _heuristic_parse_text(upload.read().decode('utf-8',errors='replace'),source)
    if name.endswith('.pdf'):
        from pypdf import PdfReader
        return _heuristic_parse_text('\n'.join((p.extract_text() or '') for p in PdfReader(upload).pages),source)
    return []


def _bytes_upload(upload):
    name=upload.name
    data=upload.read()
    upload.seek(0)
    return name,data


def read_uploaded(upload):
    """Legacy text/evidence helper retained for API/backward compatibility."""
    chunks=_uploaded_chunks(upload)
    return '\n\n'.join(chunks)


def parse_lines(text, source='text'):
    """AI-first inference for pasted/free-form text; no field/column layout required."""
    chunks=_split_text(text or '')
    all_records=[]; route_meta={}; errors=[]; ai_succeeded=True
    for idx,chunk in enumerate(chunks):
        try:
            rows,meta=_infer_chunk(chunk,'free-form text'); all_records.extend(rows); route_meta=meta
        except Exception as exc:
            errors.append(str(exc)); all_records=[]; ai_succeeded=False; break
    if ai_succeeded:
        created=[]
        for row in _dedupe_inferred(all_records):
            c=_create_candidate(row,source,row.get('evidence','') or (text or '')[:2000],'ai',{**route_meta,'chunk_count':len(chunks)})
            if c: created.append(c)
        return created
    return _heuristic_parse_text(text,source)


def parse_uploaded(upload, source='document'):
    """AI/ML interpretation of arbitrary supported files, with deterministic fallback."""
    if not upload:
        raise RuntimeError('Choose a file to import')
    name,payload=_bytes_upload(upload)
    # Use independent BytesIO copies because parsers/AI evidence extraction consume streams.
    class NamedBytesIO(io.BytesIO):
        pass
    evidence_file=NamedBytesIO(payload); evidence_file.name=name
    chunks=_uploaded_chunks(evidence_file)
    all_records=[]; errors=[]; route_meta={}; ai_succeeded=True
    for idx,chunk in enumerate(chunks):
        try:
            rows,meta=_infer_chunk(chunk,f'uploaded file {name}, chunk {idx+1}/{len(chunks)}')
            all_records.extend(rows); route_meta=meta
        except Exception as exc:
            errors.append(str(exc)); all_records=[]; ai_succeeded=False; break
    if ai_succeeded:
        created=[]
        for row in _dedupe_inferred(all_records):
            c=_create_candidate(row,source,row.get('evidence',''), 'ai', {**route_meta,'file':name,'chunk_count':len(chunks),'errors':errors})
            if c: created.append(c)
        return created
    fallback=NamedBytesIO(payload); fallback.name=name
    return _fallback_for_upload(fallback,source)


def confirm_candidate(candidate):
    """Promote an import candidate into canonical applied history and suppression.

    Exact company/role duplicates are marked handled but are not added twice.
    """
    if candidate.imported: return None
    if candidate.company and candidate.role_title:
        duplicate=Application.objects.select_related('opportunity').filter(
            status__in=['applied','reply','interview','rejected','accepted','closed'],
            opportunity__company__iexact=candidate.company.strip(),
            opportunity__title__iexact=candidate.role_title.strip(),
        ).first()
        if duplicate:
            candidate.imported=True; candidate.save(update_fields=['imported'])
            return None
    url=candidate.url or f'https://imported.invalid/{candidate.pk}'
    opp=Opportunity.objects.filter(url=url).first()
    if not opp:
        opp=Opportunity.objects.create(
            title=candidate.role_title or 'Imported prior application', company=candidate.company,
            url=url, canonical_url=(candidate.url or ''), target_url=(candidate.url or ''), channel=candidate.channel if candidate.channel in dict(Opportunity.CHANNEL) else 'unknown',
            contact_email=candidate.email, status='applied', suppressed=True,
            recommendation_reason=('Imported historical application; suppressed from discovery. '+candidate.notes[:500]).strip(),
            first_seen_by_portal=timezone.now(), last_seen=timezone.now(),
            extracted_facts={
                'imported_status':candidate.outcome_status,'imported_notes':candidate.notes,
                'import_inference_method':candidate.inference_method,
                'import_confidence':candidate.confidence,
                'synthetic_url':not bool(candidate.url),
            },
        )
    else:
        opp.status='applied'; opp.suppressed=True
        facts=opp.extracted_facts or {}; facts.update({'imported_status':candidate.outcome_status,'imported_notes':candidate.notes,'import_inference_method':candidate.inference_method,'import_confidence':candidate.confidence}); opp.extracted_facts=facts
        opp.save(update_fields=['status','suppressed','extracted_facts','updated_at'])
    app,_=Application.objects.get_or_create(opportunity=opp, defaults={'is_read':True})
    status=candidate.outcome_status if candidate.outcome_status in dict(Application.STATUS) else 'applied'
    app.status=status
    app.is_read=True
    app.date_added=timezone.now()
    # Unknown dates stay unknown. Do not turn the import timestamp into a fictitious application date.
    if candidate.date_applied:
        app.applied_at=candidate.date_applied
    app.notes=candidate.notes
    app.save()
    candidate.imported=True; candidate.save(update_fields=['imported'])
    return app
