from __future__ import annotations
import json
import re
import requests
import urllib.parse
from bs4 import BeautifulSoup

UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ScoutBox/0.8.3'
REDIRECT_BOILERPLATE=(
    'please click here if the page does not redirect automatically',
    'if you are not redirected automatically',
    'click here to continue',
    'redirecting you to',
)

def _jobposting_schema(soup):
    for tag in soup.select('script[type="application/ld+json"]'):
        try:
            data=json.loads(tag.string or tag.get_text() or '{}')
        except Exception:
            continue
        stack=data if isinstance(data,list) else [data]
        while stack:
            x=stack.pop()
            if isinstance(x,dict):
                typ=x.get('@type')
                if typ=='JobPosting' or (isinstance(typ,list) and 'JobPosting' in typ):
                    return x
                graph=x.get('@graph')
                if isinstance(graph,list): stack.extend(graph)
            elif isinstance(x,list): stack.extend(x)
    return None


def _has_jobposting_schema(soup):
    return bool(_jobposting_schema(soup))



def structured_visible_text(root):
    """Serialize visible HTML into compact section-aware text for Local/Cloud analysis.

    v0.10.121 intentionally avoids pipe-delimited flattening. A pipe turns unrelated
    DOM siblings into one sentence, which made extractors treat footer/company/related
    job locations as if they belonged to the current role. This serializer keeps block
    boundaries, emits label/value pairs on separate lines, and inserts lightweight
    section headers so downstream location, contact, and Focus extractors can reason
    about scope before asking Local AI.
    """
    if root is None:
        return ''

    def norm(value):
        return ' '.join(str(value or '').replace('\xa0',' ').split()).strip()

    def clean_line(value):
        value=norm(value)
        value=re.sub(r'\s+([:;,.])', r'\1', value)
        return value.strip(' \t\r\n')

    def section_name(text, tag=''):
        t=clean_line(text).strip(' :-–—').lower()
        if not t:
            return ''
        exact={
            'role snapshot':'CURRENT_JOB_HEADER',
            'remote from':'CURRENT_JOB_HEADER',
            'job details':'CURRENT_JOB_HEADER',
            'job description':'JOB_DESCRIPTION',
            'description':'JOB_DESCRIPTION',
            'opportunity details':'JOB_DESCRIPTION',
            'about this role':'JOB_DESCRIPTION',
            'about the role':'JOB_DESCRIPTION',
            'responsibilities':'RESPONSIBILITIES',
            'requirements':'QUALIFICATIONS',
            'qualifications':'QUALIFICATIONS',
            'minimum qualifications':'QUALIFICATIONS',
            'preferred qualifications':'QUALIFICATIONS',
            'benefits':'BENEFITS',
            'what we offer':'BENEFITS',
            'compensation':'COMPENSATION',
            'salary':'COMPENSATION',
            'pay range':'COMPENSATION',
            'application information':'APPLICATION',
            'apply now':'APPLICATION',
            'next step':'APPLICATION',
            'about the company':'COMPANY_PROFILE',
            'company profile':'COMPANY_PROFILE',
            'related jobs':'RELATED_JOBS',
            'related remote jobs':'RELATED_JOBS',
            'recommended jobs':'RELATED_JOBS',
            'similar jobs':'RELATED_JOBS',
            'keep exploring':'RELATED_JOBS',
            'more opportunities':'RELATED_JOBS',
            'footer':'FOOTER',
            'navigation':'NAVIGATION',
        }
        if t in exact:
            return exact[t]
        if re.search(r'(?i)\b(related|recommended|similar|more)\s+(?:remote\s+)?jobs?\b|keep exploring', t):
            return 'RELATED_JOBS'
        if re.search(r'(?i)\babout\s+(?:the\s+)?company\b|company profile', t):
            return 'COMPANY_PROFILE'
        if re.search(r'(?i)\b(apply now|application process|next step)\b', t):
            return 'APPLICATION'
        if re.search(r'(?i)\b(compensation|salary|base pay|pay range)\b', t) and len(t) < 80:
            return 'COMPENSATION'
        if re.search(r'(?i)\b(responsibilities|what you(?:\'|’)ll do|what you will do)\b', t) and len(t) < 100:
            return 'RESPONSIBILITIES'
        if re.search(r'(?i)\b(requirements|qualifications|about you|skills)\b', t) and len(t) < 100:
            return 'QUALIFICATIONS'
        return ''

    def is_boilerplate_section(name):
        return name in {'RELATED_JOBS','FOOTER','NAVIGATION'}

    blocks=[]
    seen=set()
    current_section=''
    total_chars=0
    max_chars=60000
    label_re=re.compile(r'(?i)^(job location|work location|location requirements?|location|remote from|office|workplace|posted(?: on)?|date posted|published|apply before|closing date|base pay range|salary|compensation|employment type|job type|work type|work model|remote status|hiring timezones?|seniority level|experience level|department|visa sponsorship|relocation)$')
    stop_names={'RELATED_JOBS','FOOTER','NAVIGATION'}

    def add_section(name):
        nonlocal current_section, total_chars
        if not name or name == current_section:
            return
        current_section=name
        marker=f'[{name}]'
        if blocks and blocks[-1] == marker:
            return
        blocks.append(marker)
        total_chars+=len(marker)+1

    def add(text, section=None, allow_duplicate=False):
        nonlocal total_chars
        text=clean_line(text)
        if not text:
            return
        if len(text)>1200:
            text=text[:1197].rstrip()+'…'
        if section:
            add_section(section)
        key=(current_section,text)
        if not allow_duplicate and key in seen:
            return
        seen.add(key)
        blocks.append(text)
        total_chars+=len(text)+1

    # Remove non-content nodes before walking. Keep anchors/text; hrefs are handled elsewhere.
    try:
        root=BeautifulSoup(str(root),'html.parser')
    except Exception:
        pass
    for bad in root(['script','style','noscript','svg','iframe','canvas','template']):
        bad.decompose()
    for tag in root.find_all(['nav','footer']):
        # Preserve explicit job-board content if a broken template used nav/footer inside main.
        txt=clean_line(tag.get_text(' ',strip=True))
        if len(txt)>300 and re.search(r'(?i)\b(job|role|responsibilit|qualification|apply)\b', txt):
            continue
        tag.decompose()

    def child_texts(node):
        out=[]
        for child in node.find_all(['div','span','strong','b','dt','dd'],recursive=False):
            t=clean_line(child.get_text(' ',strip=True))
            if t and len(t)<=260 and t not in out:
                out.append(t)
        return out

    handled=set()
    nodes=root.find_all(['h1','h2','h3','h4','h5','h6','table','dl','p','li','section','article','main','div'])
    for node in nodes:
        if total_chars>=max_chars:
            break
        if any(id(a) in handled for a in node.parents if a is not None):
            continue
        tag=(node.name or '').lower()
        node_text=clean_line(node.get_text(' ',strip=True))
        if not node_text:
            continue

        # Headings establish the next extraction scope. Related/footer/navigation scopes
        # are emitted as a boundary and then stop the current-role document walk.
        if tag in {'h1','h2','h3','h4','h5','h6'}:
            sec=section_name(node_text, tag)
            if sec in stop_names:
                add_section(sec)
                break
            if sec:
                add_section(sec)
                if sec not in {'CURRENT_JOB_HEADER','JOB_DESCRIPTION'}:
                    continue
            add(node_text, current_section or ('PAGE_TITLE' if tag=='h1' else None))
            continue

        if tag in {'main','article','section'}:
            sec=section_name(node_text[:120], tag)
            if sec in stop_names:
                add_section(sec)
                break
            # Do not flatten a large section; children will be processed in order.
            if len(node_text)>500 or node.find(['h1','h2','h3','p','li','table','dl','section','article','div'],recursive=False):
                continue

        if tag=='table':
            handled.add(id(node))
            for tr in node.find_all('tr'):
                cells=[clean_line(c.get_text(' ',strip=True)) for c in tr.find_all(['th','td'],recursive=False)]
                cells=[c for c in cells if c]
                if not cells:
                    continue
                if len(cells)>=2 and len(cells[0])<=80:
                    add(f'{cells[0].rstrip(":")} : {" ".join(cells[1:])}')
                else:
                    add(' '.join(cells))
            continue

        if tag=='dl':
            handled.add(id(node)); pending=''
            for item in node.find_all(['dt','dd'],recursive=False):
                text=clean_line(item.get_text(' ',strip=True))
                if not text:
                    continue
                if item.name=='dt':
                    pending=text.rstrip(':')
                elif pending:
                    add(f'{pending}: {text}'); pending=''
                else:
                    add(text)
            if pending: add(pending)
            continue

        direct=child_texts(node)
        if len(direct)>=2:
            first=direct[0].rstrip(':')
            if label_re.match(first):
                # Emit one label/value line. Do not use pipes; following values remain adjacent
                # within the same scoped section without becoming a fake combined sentence.
                add(f'{first}: {" ".join(direct[1:4])}', 'CURRENT_JOB_HEADER' if label_re.match(first) else current_section)
                handled.add(id(node))
                continue
            # Jobicy and similar role snapshots frequently render "Remote from" and the
            # value as sibling text nodes inside a parent whose children are not semantic.
            for idx,item in enumerate(direct[:-1]):
                if label_re.match(item.rstrip(':')):
                    add(f'{item.rstrip(":")}: {direct[idx+1]}', 'CURRENT_JOB_HEADER')
                    handled.add(id(node))
                    break
            if id(node) in handled:
                continue

        if tag in {'p','li'}:
            if node.find_parent(['table','dl']) is None:
                if not node.find(['p','li','table','dl','section','article'],recursive=False):
                    sec=section_name(node_text)
                    if sec in stop_names:
                        add_section(sec); break
                    if sec:
                        add_section(sec); continue
                    add(node_text)
            continue

        # Leaf divs often contain compact key facts. Large container divs are skipped so
        # their children define structure instead of one flattened blob.
        if tag=='div':
            if node.find(['p','li','table','dl','section','article','h1','h2','h3','h4','h5','h6'],recursive=False):
                continue
            sec=section_name(node_text)
            if sec in stop_names:
                add_section(sec); break
            if sec:
                add_section(sec); continue
            if len(node_text)<=360:
                m=re.match(r'(?i)^(job location|work location|location requirements?|remote from|location|posted(?: on)?|date posted|published|apply before|base pay range|salary|compensation|employment type|job type|work type|work model|remote status|hiring timezones?|seniority level|experience level|department)\s*[:\-]?\s+(.+)$',node_text)
                if m:
                    add(f'{m.group(1).rstrip(":")}: {m.group(2)}','CURRENT_JOB_HEADER')
                else:
                    add(node_text)

    if not blocks:
        return clean_visible_text(root.get_text('\n',strip=True))

    # Clean repeated blank lines and accidental pipe separators left in source text while
    # preserving legitimate technical pipes in short code-ish phrases.
    text='\n'.join(blocks)
    text=re.sub(r'\s*\|\s*', ' ', text)
    text=re.sub(r'\n{3,}', '\n\n', text)
    return clean_visible_text(text)


def structured_visible_sections(root):
    """Return a simple section map from structured_visible_text output.

    This helper lets new extractors consume scoped text without reparsing HTML. Existing
    callers can continue to use structured_visible_text as a string.
    """
    text=structured_visible_text(root)
    sections={}
    current='UNSCOPED'
    for raw in text.splitlines():
        line=raw.strip()
        if not line:
            continue
        m=re.fullmatch(r'\[([A-Z0-9_ -]{3,60})\]', line)
        if m:
            current=m.group(1).strip().replace(' ','_')
            sections.setdefault(current, [])
        else:
            sections.setdefault(current, []).append(line)
    return {k:'\n'.join(v).strip() for k,v in sections.items() if v}

def extract_followup_links(root, base_url, limit=160):
    """Return canonical-ish HTML links with anchor/context for bounded Local discovery."""
    out=[]; seen=set()
    if root is None:
        return out
    for a in root.find_all('a',href=True):
        href=str(a.get('href') or '').strip()
        if not href or href.startswith(('#','mailto:','tel:','javascript:')):
            continue
        try:
            url=urllib.parse.urljoin(base_url,href)
            parts=urllib.parse.urlsplit(url)
            if parts.scheme not in ('http','https') or not parts.netloc:
                continue
            url=urllib.parse.urlunsplit((parts.scheme,parts.netloc,parts.path,parts.query,''))
        except Exception:
            continue
        if url in seen:
            continue
        seen.add(url)
        anchor=' '.join(a.get_text(' ',strip=True).split())[:300]
        parent=a.find_parent(['li','p','td','div','section'])
        context=' '.join(parent.get_text(' ',strip=True).split())[:600] if parent else anchor
        out.append({'url':url[:1500],'anchor':anchor,'context':context})
        if len(out)>=max(1,int(limit or 160)):
            break
    return out


def clean_visible_text(text):
    text=(text or '').replace('\xa0',' ')
    for phrase in REDIRECT_BOILERPLATE:
        text=re.sub(re.escape(phrase), ' ', text, flags=re.I)
    text=re.sub(r'[ \t]+',' ',text)
    text=re.sub(r'\n[ \t]+','\n',text)
    text=re.sub(r'\n{3,}','\n\n',text)
    return text.strip()

_LANGUAGE_PROBES={
    'en':[' the ',' and ',' with ',' for ',' you ',' experience ',' requirements ',' responsibilities ',' role ',' team ',' work ',' skills ',' software ',' engineer ',' company ',' development '],
    'de':[' der ',' die ',' und ',' mit ',' für ',' erfahrung ',' aufgaben ',' kenntnisse ',' wir ',' sie '],
    'fr':[' le ',' la ',' les ',' et ',' avec ',' pour ',' expérience ',' compétences ',' nous ',' vous '],
    'es':[' el ',' la ',' los ',' y ',' con ',' para ',' experiencia ',' requisitos ',' nosotros ',' trabajo '],
    'pt':[' o ',' a ',' os ',' e ',' com ',' para ',' experiência ',' requisitos ',' trabalho ',' você '],
    'it':[' il ',' la ',' e ',' con ',' per ',' esperienza ',' requisiti ',' lavoro ',' noi ',' competenze '],
}


def _language_probe_scores(text):
    low=' '+str(text or '').lower()+' '
    return {lang:sum(low.count(w) for w in words) for lang,words in _LANGUAGE_PROBES.items()}


def detect_language(text):
    sample=(text or '')[:12000]
    if not sample.strip(): return ''
    counts={
        'ko':len(re.findall(r'[\uac00-\ud7af]',sample)),
        'ja':len(re.findall(r'[\u3040-\u30ff]',sample)),
        'zh':len(re.findall(r'[\u4e00-\u9fff]',sample)),
        'ru':len(re.findall(r'[\u0400-\u04ff]',sample)),
    }
    letters=max(1,len(re.findall(r'\w',sample,re.UNICODE)))
    k=max(counts,key=counts.get)
    if counts[k]/letters>.08:
        # Han alone may be Japanese; kana is checked first through ja count.
        return k
    scores=_language_probe_scores(sample)
    best=max(scores,key=scores.get)
    return best if scores[best]>=2 else 'en'


def primarily_english(text, detected_code=''):
    """Return True when English is the dominant readable language of a page.

    Local GPU discovery uses this as a quality gate. It deliberately tolerates snippets,
    names, quotations, code comments, and a few sentences in CJK/Korean/other languages;
    it rejects pages whose *main body* is clearly non-English. Cloud Web discovery does
    not use this gate because the cloud research pass can translate/ground foreign pages.
    """
    sample=' '.join(str(text or '')[:30000].split())
    if not sample:
        return True

    latin=len(re.findall(r'[A-Za-zÀ-ÖØ-öø-ÿ]',sample))
    han=len(re.findall(r'[\u4e00-\u9fff]',sample))
    kana=len(re.findall(r'[\u3040-\u30ff]',sample))
    hangul=len(re.findall(r'[\uac00-\ud7af]',sample))
    cyrillic=len(re.findall(r'[\u0400-\u04ff]',sample))
    major_non_latin=han+kana+hangul+cyrillic
    script_letters=max(1,latin+major_non_latin)
    foreign_script_ratio=major_non_latin/script_letters

    # A foreign paragraph or translated sentence is fine. A page dominated by a foreign
    # script is not useful for Local GPU discovery and tends to generate noisy matches.
    if major_non_latin>=80 and foreign_script_ratio>=0.38:
        return False

    scores=_language_probe_scores(sample)
    en=scores.get('en',0)
    other=max((v for k,v in scores.items() if k!='en'),default=0)
    code=str(detected_code or detect_language(sample) or '').lower().split('-',1)[0]
    if code in {'zh','ja','ko','ru'} and foreign_script_ratio>=0.24 and en<8:
        return False
    # Latin-script pages also need an English-dominance check. The previous shortcut
    # accepted any long Latin page, which accidentally let Spanish/French/etc. pages
    # through Local GPU discovery. Require a meaningful non-English probe advantage
    # before rejecting, so names and a few translated paragraphs remain harmless.
    if code not in {'','en'} and other>=5 and other>en*1.35:
        return False
    if latin>=180 and foreign_script_ratio<=0.18:
        if other>=6 and other>en*1.35:
            return False
        return True
    # When evidence is mixed or sparse, keep it. This is a dominance filter, not a
    # requirement that every sentence be English.
    return True





def probe_url_health(url, timeout=15, capture_text=False, max_content_bytes=180000):
    """Passive reachability/status probe, optionally retaining a bounded HTML text sample.

    TLS remains deliberately relaxed only for this passive health probe. The optional text
    sample lets the scheduled Opportunity checker distinguish a live HTTP shell from a page
    that still contains the actual job, without downloading unbounded response bodies.
    """
    result={'ok':False,'url':str(url or ''),'target_url':str(url or ''),'http_status':None,'error':'','tls_verification':'disabled-for-health-probe-only','content_sample':'','content_type':'','response_bytes':0,'page_title':'','h1_text':''}
    if not str(url or '').startswith(('http://','https://')):
        result['error']='Invalid target URL'; return result
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        r=requests.get(str(url),headers={'User-Agent':UA,'Accept-Language':'en-US,en;q=0.8'},timeout=timeout,allow_redirects=True,verify=False,stream=True)
        result['http_status']=int(r.status_code or 0)
        result['target_url']=r.url or str(url)
        result['content_type']=str(r.headers.get('Content-Type') or '')[:200]
        try: result['response_bytes']=max(0,int(r.headers.get('Content-Length') or 0))
        except Exception: result['response_bytes']=0
        result['ok']=True
        if capture_text and result['http_status']==200 and ('html' in result['content_type'].lower() or not result['content_type']):
            chunks=[]; total=0
            for chunk in r.iter_content(chunk_size=16384):
                if not chunk: continue
                remaining=max_content_bytes-total
                if remaining<=0: break
                chunks.append(chunk[:remaining]); total+=min(len(chunk),remaining)
                if total>=max_content_bytes: break
            raw=b''.join(chunks)
            if raw:
                if not result['response_bytes']: result['response_bytes']=len(raw)
                soup=BeautifulSoup(raw,'html.parser')
                result['page_title']=' '.join((soup.title.get_text(' ',strip=True) if soup.title else '').split())[:500]
                h1=soup.find('h1'); result['h1_text']=' '.join((h1.get_text(' ',strip=True) if h1 else '').split())[:800]
                for tag in soup(['script','style','noscript','svg']): tag.decompose()
                result['content_sample']=structured_visible_text(soup)[:14000]
        r.close()
        return result
    except Exception as exc:
        result['error']=str(exc)[:500]
        return result

def fetch_target(url, fallback_title='', fallback_text='', timeout=18):
    """Fetch a public HTML target using a bounded streaming body.

    Discovery does not download PDFs, archives, media, office documents or other large
    binary bodies merely to search them.  Content-Type/final URL are inspected before
    consuming the response body; normal HTML/text is capped to keep direct discovery
    inexpensive even when a server omits Content-Length.
    """
    result={
        'ok':False,'search_url':url or '','target_url':url or '','title':fallback_title or '',
        'text':clean_visible_text(fallback_text),'html':'','bytes':0,'content_type':'','is_pdf':False,
        'language_code':detect_language(fallback_text),'links':[],'has_jobposting_schema':False,'jobposting_title':'','jobposting_date_posted':'','jobposting_valid_through':'','jobposting_location':'','jobposting_employment_type':'','h1_title':'','document_title':'','error':'','http_status':None,'terminal_not_found':False,'response_headers':{},'skipped_binary':False,'declared_bytes':0,
    }
    if not (url or '').startswith(('http://','https://')):
        result['error']='Invalid target URL'; return result
    r=None
    try:
        r=requests.get(url,headers={'User-Agent':UA,'Accept-Language':'en-US,en;q=0.8'},timeout=timeout,allow_redirects=True,stream=True)
        result['http_status']=int(r.status_code or 0); result['target_url']=r.url or url
        result['response_headers']={'last_modified':r.headers.get('Last-Modified',''),'date':r.headers.get('Date',''),'etag':r.headers.get('ETag','')}
        try: result['declared_bytes']=max(0,int(r.headers.get('Content-Length') or 0))
        except Exception: result['declared_bytes']=0
        if r.status_code in (404,410):
            result['terminal_not_found']=True; result['text']=''; result['html']=''; result['error']=f'HTTP {r.status_code}: target page is not available'; return result
        r.raise_for_status(); result['ok']=True
        ctype=(r.headers.get('Content-Type') or '').lower(); result['content_type']=ctype
        final_path=result['target_url'].lower().split('?',1)[0]
        result['is_pdf']='application/pdf' in ctype or final_path.endswith('.pdf')
        binary_types=('application/pdf','application/zip','application/x-zip','application/octet-stream','application/vnd.ms-','application/vnd.openxmlformats','image/','audio/','video/','font/')
        binary_exts=('.pdf','.zip','.7z','.rar','.gz','.tar','.tgz','.doc','.docx','.xls','.xlsx','.ppt','.pptx','.dmg','.exe','.iso','.png','.jpg','.jpeg','.gif','.webp','.mp3','.mp4','.mov','.avi')
        likely_binary=result['is_pdf'] or any(token in ctype for token in binary_types) or final_path.endswith(binary_exts)
        if likely_binary:
            result['skipped_binary']=True
            result['language_code']=detect_language(result['text'])
            return result
        # Skip unexpectedly huge non-text payloads before consumption when length is known.
        textual=(not ctype) or any(x in ctype for x in ('text/','html','xml','json','javascript'))
        if result['declared_bytes']>3_000_000 and not textual:
            result['skipped_binary']=True
            return result
        max_body=2_500_000
        chunks=[]; total=0
        for chunk in r.iter_content(chunk_size=32768):
            if not chunk: continue
            remaining=max_body-total
            if remaining<=0: break
            take=chunk[:remaining]; chunks.append(take); total+=len(take)
            if total>=max_body: break
        raw=b''.join(chunks); result['bytes']=len(raw)
        if not raw:
            result['language_code']=detect_language(result['text']); return result
        soup=BeautifulSoup(raw,'html.parser')
        schema=_jobposting_schema(soup)
        result['has_jobposting_schema']=bool(schema)
        if isinstance(schema,dict):
            result['jobposting_title']=clean_visible_text(str(schema.get('title') or schema.get('name') or ''))[:300]
            hiring=schema.get('hiringOrganization') or schema.get('hiringOrganisation') or {}
            if isinstance(hiring,list):
                hiring=next((x for x in hiring if isinstance(x,(dict,str))),{})
            if isinstance(hiring,dict):
                hiring=hiring.get('name') or hiring.get('legalName') or ''
            result['jobposting_company']=clean_visible_text(str(hiring or ''))[:220]
            result['jobposting_date_posted']=clean_visible_text(str(schema.get('datePosted') or ''))[:120]
            result['jobposting_valid_through']=clean_visible_text(str(schema.get('validThrough') or ''))[:120]
            result['jobposting_employment_type']=clean_visible_text(str(schema.get('employmentType') or ''))[:200]
            locations=schema.get('jobLocation') or schema.get('applicantLocationRequirements') or ''
            try: result['jobposting_location']=clean_visible_text(json.dumps(locations,ensure_ascii=False) if not isinstance(locations,str) else locations)[:1200]
            except Exception: result['jobposting_location']=clean_visible_text(str(locations))[:1200]
        h=soup.find('h1')
        if h: result['h1_title']=clean_visible_text(h.get_text(' ',strip=True))[:300]
        if soup.title: result['document_title']=clean_visible_text(soup.title.get_text(' ',strip=True))[:300]
        title=result['jobposting_title'] or result['h1_title'] or result['document_title']
        if title: result['title']=clean_visible_text(title)[:300]
        for bad in soup(['script','style','noscript','svg','iframe','form','nav']): bad.extract()
        content=soup.select_one('[class*=job-description], [id*=job-description], [class*=jobDescription], main, article') or soup.body or soup
        result['html']=str(content)[:90000]
        text=structured_visible_text(content)[:45000]
        if text: result['text']=text
        result['links']=extract_followup_links(content,result['target_url'],limit=180)
        result['language_code']=detect_language(result['text'])
        return result
    except Exception as exc:
        result['error']=str(exc); return result
    finally:
        try:
            if r is not None: r.close()
        except Exception: pass
