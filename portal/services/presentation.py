import html
import re
import bleach

EMPTY_WORDS={'','blank','unknown','n/a','na','none','null','not specified','not available','-','—'}
ALLOWED_TAGS=['p','br','strong','b','em','i','u','ul','ol','li','a','table','thead','tbody','tr','th','td','h1','h2','h3','h4','blockquote','code','pre','hr']
ALLOWED_ATTRS={'a':['href','title','target','rel'],'th':['colspan','rowspan'],'td':['colspan','rowspan']}


def clean_placeholder(value, fallback=''):
    text=str(value or '').strip()
    return fallback if text.lower() in EMPTY_WORDS else text


def rich_html(value):
    raw=str(value or '').strip()
    if not raw:
        return ''
    looks_html=bool(re.search(r'<\s*(p|br|div|strong|b|em|i|u|ul|ol|li|table|h[1-6]|a)\b',raw,re.I))
    if looks_html:
        cleaned=bleach.clean(raw,tags=ALLOWED_TAGS,attributes=ALLOWED_ATTRS,protocols=['http','https','mailto'],strip=True)
        cleaned=bleach.linkify(cleaned,callbacks=[lambda attrs,new=False: {**attrs,(None,'target'):'_blank',(None,'rel'):'noreferrer noopener'}])
        return cleaned
    # Preserve readable paragraphs even when crawlers collapsed line breaks.
    raw=re.sub(r'\r\n?', '\n', raw)
    blocks=[x.strip() for x in re.split(r'\n\s*\n+',raw) if x.strip()]
    if len(blocks)==1 and len(raw)>700:
        # Break long plain text at likely sentence/section boundaries without mangling URLs.
        sentences=re.split(r'(?<=[.!?])\s+(?=[A-Z][A-Za-z])',raw)
        blocks=[]; buf=[]; chars=0
        for sent in sentences:
            buf.append(sent); chars+=len(sent)
            if chars>=550:
                blocks.append(' '.join(buf)); buf=[]; chars=0
        if buf: blocks.append(' '.join(buf))
    out=''.join(f'<p>{bleach.linkify(html.escape(b),parse_email=True)}</p>' for b in blocks)
    return out


def human_facts(data):
    """Flatten user-facing extraction facts while hiding internal/debug structures."""
    if not isinstance(data,dict): return []
    skip={'discovery_query','discovery_provenance','rediscovered_query','rediscovered_profile_matches','search_pre_score','raw_search_hits_consolidated','facebook_mode','cloud_discovery','cloud_discovery_provider','cloud_discovery_model','role_page_classification','resolved_url','description_html','translation','company_research_raw','ai_job_summary'}
    labels={
        'employmentType':'Employment type','employment_type':'Employment type','jobLocation':'Location','salary':'Compensation','salary_currency':'Currency','salary_period':'Pay period',
        'work_authorization':'Work authorization','visa_sponsorship':'Visa sponsorship','experience':'Experience','skills':'Skills','requirements':'Requirements','benefits':'Benefits','remote':'Remote',
        'geography_fit':'Location fit','application_history':'Application history','cv_profile_matches':'Resume matches','datePosted':'Posted date','validThrough':'Valid through',
    }
    out=[]
    def add(label,val):
        if val is None or val is False: return
        if isinstance(val,str):
            val=clean_placeholder(val)
            if not val:return
        if isinstance(val,list):
            parts=[clean_placeholder(x) for x in val if clean_placeholder(x)]
            if not parts:return
            val=', '.join(parts[:12])
        elif isinstance(val,dict):
            # Keep useful compact dictionaries human readable.
            pieces=[]
            for k,v in val.items():
                if k in ('metadata','raw','evidence') or v in (None,'',False,[]): continue
                vv=', '.join(map(str,v)) if isinstance(v,list) else str(v)
                vv=clean_placeholder(vv)
                if vv: pieces.append(f'{k.replace("_"," ").title()}: {vv}')
            if not pieces:return
            val='; '.join(pieces[:8])
        out.append((label,str(val)))
    for k,v in data.items():
        if k in skip: continue
        add(labels.get(k,k.replace('_',' ').strip().title()),v)
    return out


def confidence_band(value):
    try:n=int(value or 0)
    except Exception:n=0
    if n>=75:return 'High'
    if n>=45:return 'Medium'
    return 'Low'


def simple_job_html(value):
    """Render noisy scraped job HTML as compact, safe reading text.

    Keep only paragraphs, line breaks, emphasis and links. Empty blocks and repeated
    breaks are removed. Soft-wrapped lines are joined, while real paragraph breaks
    are kept; very short adjacent fragments are merged only when they look like a
    crawler split rather than complete prose.
    """
    raw=str(value or '').strip()
    if not raw:
        return ''
    raw=re.sub(r'\r\n?', '\n', raw)
    # Turn common block structures into paragraph boundaries before sanitising.
    raw=re.sub(r'<\s*(?:div|section|article|header|footer|aside|main|h[1-6]|li|tr|blockquote)[^>]*>', '<p>', raw, flags=re.I)
    raw=re.sub(r'<\s*/\s*(?:div|section|article|header|footer|aside|main|h[1-6]|li|tr|blockquote)\s*>', '</p>', raw, flags=re.I)
    raw=re.sub(r'<\s*(?:td|th)[^>]*>', ' ', raw, flags=re.I)
    raw=re.sub(r'<\s*/\s*(?:td|th)\s*>', ' ', raw, flags=re.I)
    # Plain-text crawler output: single newlines are soft wraps, blank lines are
    # deliberate paragraph boundaries.
    if not re.search(r'<\s*(?:p|br|strong|b|a)\b',raw,re.I):
        # If a scraper collapsed an entire page into one line, rebuild conservative
        # paragraph breaks after a few complete sentences instead of showing a dump.
        if '\n' not in raw and len(raw)>650:
            sentences=re.split(r'(?<=[.!?])\s+(?=[A-Z0-9])',raw)
            groups=[]; buf=[]; chars=0
            for sentence in sentences:
                buf.append(sentence); chars+=len(sentence)
                if len(buf)>=4 or chars>=560:
                    groups.append(' '.join(buf)); buf=[]; chars=0
            if buf: groups.append(' '.join(buf))
            if len(groups)>1:
                raw='\n\n'.join(groups)
            elif len(raw)>650:
                # Some sources return a single punctuation-poor blob. Split it into
                # readable word groups rather than presenting one wall of text.
                words=raw.split()
                chunks=[]
                for i in range(0,len(words),85):
                    chunks.append(' '.join(words[i:i+85]))
                if len(chunks)>1:
                    raw='\n\n'.join(chunks)
        raw=html.escape(raw)
        raw=re.sub(r'\n{3,}', '\n\n', raw)
        raw=raw.replace('\n\n','</p><p>').replace('\n','<br>')
        raw='<p>'+raw+'</p>'
    cleaned=bleach.clean(raw,tags=['p','br','strong','b','a'],attributes={'a':['href','title','target','rel']},protocols=['http','https','mailto'],strip=True)
    cleaned=bleach.linkify(cleaned,callbacks=[lambda attrs,new=False: {**attrs,(None,'target'):'_blank',(None,'rel'):'noreferrer noopener'}])
    cleaned=re.sub(r'<p>\s*(?:<br\s*/?>\s*)*</p>', '', cleaned, flags=re.I)
    cleaned=re.sub(r'(?:<br\s*/?>\s*){3,}', '<br><br>', cleaned, flags=re.I)
    # Encode paragraph boundaries separately from BR soft-wraps.
    cleaned=re.sub(r'</p>\s*<p[^>]*>', '\n\n', cleaned, flags=re.I)
    cleaned=re.sub(r'</?p[^>]*>', '', cleaned, flags=re.I)
    cleaned=re.sub(r'(?:<br\s*/?>\s*){2}', '\n\n', cleaned, flags=re.I)
    cleaned=re.sub(r'<br\s*/?>', '\n', cleaned, flags=re.I)
    blocks=[]
    for block in re.split(r'\n\s*\n+',cleaned):
        # Any single-newline wrapping inside a paragraph becomes ordinary spacing.
        block=' '.join(x.strip() for x in re.split(r'\n+',block) if x.strip())
        block=re.sub(r'\s{2,}',' ',block).strip()
        text=html.unescape(re.sub(r'<[^>]+>',' ',block))
        text=re.sub(r'\s+',' ',text).strip()
        if not text:
            continue
        if blocks:
            prev_html,prev_text=blocks[-1]
            # Merge only genuinely short hard blocks; this catches crawler fragments
            # such as "Requirements:" + "C / C++" without swallowing prose paragraphs.
            if len(text)<=32 and len(prev_text)<=70 and len(prev_text)+1+len(text)<=110 and (prev_text.endswith((':',',',';','/','-','–','—')) or not re.search(r'[.!?]$',prev_text)):
                blocks[-1]=[prev_html+' '+block,prev_text+' '+text]
                continue
        blocks.append([block,text])
    out=''.join('<p>'+frag+'</p>' for frag,_ in blocks)
    # Browser rendering now has no empty paragraphs and never more than one normal
    # paragraph gap (equivalent to at most two source line breaks).
    return out.strip()
