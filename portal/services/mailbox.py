import copy, email, imaplib, re, uuid, mimetypes, html as html_lib
from urllib.parse import unquote
from pathlib import Path
from email.message import EmailMessage
from email.header import decode_header, make_header
from email.utils import getaddresses, parsedate_to_datetime, format_datetime
import bleach
from bleach.css_sanitizer import CSSSanitizer
from django.utils import timezone
from django.db.models import Q
from portal.models import EmailProfile, Application, MailEvent, Contact, PortalSettings, ImportCandidate, Opportunity, CompanyLead, AuditLog
from .crypto import decrypt
from .company_research import company_summary_from_intel, stored_company_context, enrich_company_intel_from_retained, company_info_has_display_data
from .cloud_budget import usage_context
from .selectivity import current as selectivity_current, contact_policy, contact_identity_verified
from .location_values import parse_location_items, legacy_location_text

GENERIC_LOCALPARTS={'jobs','job','careers','career','recruiting','recruitment','recruit','recruiter','recruiters','talent','hr','askhr','humanresources','people','peopleops','people-ops','hello','info','contact','contacts','sales','marketing','campaign','campaigns','communications','community','partnerships','businessdevelopment','business-development','support','help','service','customer','customerservice','admin','office','team','work','billing','enquiries','inquiries','noreply','no-reply','donotreply','applications','application','apply','hiring'}
NON_CONTACT_MARKERS={'gdpr','privacy','privacyoffice','privacypolicy','dataprotection','datarequest','datarequests','privacyrequest','privacyrequests','dpo','eeo','eeocompliance','compliance','legal','legalnotice','terms','termsconditions','termsofuse','abuse','security','securityteam','dmca','copyright','press','media','investorrelations','noreply','donotreply','mailerdaemon','disability','disabilityadministrator','accommodation','accommodations','accomodation','accomodations','accessibility','reasonableaccommodation'}
KNOWN_NON_CONTACT_EMAILS={'taops@marvell.com','help.join@vertiv.com'}
NON_CONTACT_CONTEXT_PHRASES=(
    'reasonable accommodation','request an accommodation','requires an accommodation','accommodation during',
    'accommodation in the application','accommodation in the selection','accommodation to participate',
    'applicant with a disability','applicants with disabilities','because of a disability','disability-related',
    'accessibility assistance','accessibility support','difficulty accessing','difficulty using this website',
    'unable to access','equal employment opportunity','eeo accommodation','hr helpdesk',
)
FORWARDED_HEADER_RE=re.compile(r'(?im)^\s*(From|Sent|Date|To|Cc|Subject)\s*:\s*(.+?)\s*$')
FORWARD_MARKERS=('---------- Forwarded message ---------','Begin forwarded message:','Original Message','Forwarded Message')


def active_profile():
    return EmailProfile.objects.filter(active=True).first()


def connect(profile=None):
    profile=profile or active_profile()
    if not profile: raise RuntimeError('No active email profile')
    if not profile.imap_host: raise RuntimeError('IMAP host is not configured')
    cls=imaplib.IMAP4_SSL if profile.imap_ssl else imaplib.IMAP4
    im=cls(profile.imap_host,profile.imap_port,timeout=15)
    im.login(profile.imap_username,decrypt(profile.imap_password_enc))
    return im


def folders(profile=None):
    profile=profile or active_profile()
    im=connect(profile)
    try:
        # The bundled/internal mailbox is frequently empty on first launch. Create the
        # three mapped system folders before LIST so the browser always exposes Inbox,
        # Drafts and Sent even before a test message has been populated.
        if profile and profile.template == 'internal':
            for name in (profile.inbox_folder or 'INBOX', profile.drafts_folder or 'Drafts', profile.sent_folder or 'Sent'):
                try: ensure_folder(im,name)
                except Exception: pass
        typ,data=im.list(); out=[]
        if typ=='OK':
            for raw in data:
                text=raw.decode(errors='replace')
                quoted=re.findall(r'"([^\"]+)"\s*$',text)
                name=quoted[-1] if quoted else text.split()[-1].strip('"')
                if name and name not in out: out.append(name)
        # Some lightweight IMAP servers do not return newly-created folders until the
        # next connection. Keep the configured mappings visible in this browser response.
        if profile:
            for name in (profile.inbox_folder or 'INBOX', profile.drafts_folder or 'Drafts', profile.sent_folder or 'Sent'):
                if name and name not in out: out.append(name)
        return out
    finally: im.logout()


def ensure_folder(im,name):
    typ,_=im.select(f'"{name}"')
    if typ!='OK':
        im.create(name); typ,_=im.select(f'"{name}"')
    return typ=='OK'


def _uids_for_header(im,folder,header,value):
    ensure_folder(im,folder)
    typ,data=im.uid('search',None,'HEADER',header,f'"{value}"')
    return data[0].decode().split() if typ=='OK' and data and data[0] else []


def _delete_uid(im,uid):
    if not uid: return False
    typ,_=im.uid('store',str(uid),'+FLAGS','(\\Deleted)')
    if typ=='OK': im.expunge(); return True
    return False


def body_html(msg):
    parts=[]
    if msg.is_multipart():
        walk=msg.walk()
    else:
        walk=[msg]
    for part in walk:
        if part.get_content_type()!='text/html' or 'attachment' in (part.get('Content-Disposition','') or '').lower(): continue
        try:
            payload=part.get_payload(decode=True) or b''; charset=part.get_content_charset() or 'utf-8'
            parts.append(payload.decode(charset,errors='replace'))
        except Exception: pass
    return _sanitize_html('\n'.join(parts))


def _sanitize_html(value):
    # Email previews need ordinary newsletter/layout CSS, but must not execute scripts or
    # active browser content. Keep common structural tags, classes and safe inline CSS.
    raw=value or ''
    raw=re.sub(r'(?is)<script\b[^>]*>.*?</script\s*>','',raw)
    raw=re.sub(r'(?is)<style\b([^>]*)>(.*?)</style\s*>',lambda m:'<style'+m.group(1)+'>'+re.sub(r'(?is)@import\s+[^;]+;|url\s*\([^)]*\)|expression\s*\([^)]*\)','',m.group(2))+'</style>',raw)
    css=CSSSanitizer(allowed_css_properties=[
        'color','background','background-color','font','font-family','font-size','font-style','font-weight','line-height','text-align','text-decoration','text-transform','white-space',
        'margin','margin-top','margin-right','margin-bottom','margin-left','padding','padding-top','padding-right','padding-bottom','padding-left',
        'border','border-top','border-right','border-bottom','border-left','border-color','border-style','border-width','border-radius',
        'width','min-width','max-width','height','min-height','max-height','display','vertical-align','list-style','list-style-type','table-layout','border-collapse','border-spacing'
    ])
    tags=['a','p','br','div','span','ul','ol','li','strong','b','em','i','code','pre','blockquote','style','table','thead','tbody','tfoot','tr','th','td','h1','h2','h3','h4','h5','h6','hr','img']
    attrs={'*':['class','id','style','title','align','width','height'],'a':['href','title','target','rel'],'img':['src','alt','title','width','height'],'td':['colspan','rowspan','width','height','align','valign'],'th':['colspan','rowspan','width','height','align','valign']}
    return bleach.clean(raw,tags=tags,attributes=attrs,protocols=['http','https','mailto','data'],css_sanitizer=css,strip=True)


def _attach_file(msg, field):
    if not field: return
    try:
        p=Path(field.path)
        ctype,_=mimetypes.guess_type(str(p)); maintype,subtype=(ctype or 'application/octet-stream').split('/',1)
        msg.add_attachment(p.read_bytes(),maintype=maintype,subtype=subtype,filename=p.name)
    except Exception:
        pass


def save_draft(application, force_create=False):
    profile=active_profile()
    if not profile: raise RuntimeError('No active email profile')
    now=timezone.now()
    if application.draft_suppressed_until and application.draft_suppressed_until>now and not force_create:
        raise RuntimeError(f'Draft creation suppressed until {application.draft_suppressed_until:%Y-%m-%d}. Use Create Draft Anyway to override.')
    im=connect(profile)
    try:
        folder=profile.drafts_folder or 'Drafts'; ensure_folder(im,folder)
        msgid=application.imap_message_id or f'<portal-app-{application.pk}-{uuid.uuid4().hex[:12]}@draft.local>'
        # Reconcile by stable Message-ID before relying on an old UID. Subject is intentionally ignored.
        candidates=_uids_for_header(im,folder,'Message-ID',msgid)
        if not candidates and application.imap_message_id:
            sent_matches=_uids_for_header(im,profile.sent_folder or 'Sent','Message-ID',msgid)
            if sent_matches and not force_create:
                application.status='applied'; application.applied_at=application.applied_at or timezone.now(); application.date_added=timezone.now(); application.save(update_fields=['status','applied_at','date_added','updated_at'])
                application.opportunity.status='applied'; application.opportunity.save(update_fields=['status','updated_at'])
                raise RuntimeError('This portal-managed Message-ID is already present in the IMAP Sent folder. It will not be recreated as a draft. Use the manual override only if you intentionally need a new draft.')
            ensure_folder(im,folder)
        for uid in set(([application.imap_draft_uid] if application.imap_draft_uid else [])+candidates): _delete_uid(im,uid)
        msg=EmailMessage()
        msg['From']=profile.imap_email
        if application.opportunity.contact_email: msg['To']=application.opportunity.contact_email
        msg['Subject']=application.email_subject or f'Application: {application.opportunity.title}'
        msg['Message-ID']=msgid; msg['X-ToughDev-Portal-Application-ID']=str(application.pk)
        if application.email_mode=='html':
            html=_sanitize_html(application.email_body)
            plain=BeautifulText.from_html(html)
            msg.set_content(plain); msg.add_alternative(html,subtype='html')
        else: msg.set_content(application.email_body or '')
        # Prefer explicitly selected entries from persistent Prepared Files history.
        # If none are selected for a document kind, retain the legacy generated-file flags
        # and finally fall back to the selected source Resume/Cover Letter.
        selected=list(application.prepared_files.filter(selected_for_email=True))
        selected_cv=[x for x in selected if x.document_kind=='cv']
        selected_cover=[x for x in selected if x.document_kind=='cover']
        if selected_cv:
            for item in selected_cv: _attach_file(msg,item.file)
        else:
            resume_prepared=bool(application.attach_generated_cv or application.attach_generated_cv_pdf)
            if resume_prepared:
                if application.attach_generated_cv: _attach_file(msg,application.generated_cv)
                if application.attach_generated_cv_pdf: _attach_file(msg,application.generated_cv_pdf)
            else:
                _attach_file(msg,application.cv.file if application.cv else None)
        if selected_cover:
            for item in selected_cover: _attach_file(msg,item.file)
        else:
            cover_prepared=bool(application.attach_generated_cover or application.attach_generated_cover_pdf)
            if cover_prepared:
                if application.attach_generated_cover: _attach_file(msg,application.generated_cover)
                if application.attach_generated_cover_pdf: _attach_file(msg,application.generated_cover_pdf)
            else:
                _attach_file(msg,application.cover_letter.file if application.cover_letter else None)
        typ,_=im.append(folder,'(\\Draft)',imaplib.Time2Internaldate(timezone.now().timestamp()),msg.as_bytes())
        if typ!='OK': raise RuntimeError('IMAP APPEND failed')
        fresh=_uids_for_header(im,folder,'Message-ID',msgid)
        uid=fresh[-1] if fresh else ''
        application.imap_draft_folder=folder; application.imap_draft_uid=uid; application.imap_message_id=msgid; application.status='draft'; application.draft_suppressed_until=None; application.draft_suppression_reason=''; application.save()
        MailEvent.objects.create(kind='draft',application=application,subject=msg['Subject'],sender=profile.imap_email,recipients=application.opportunity.contact_email,folder=folder,uid=uid,message_id=msgid,body_excerpt=(application.email_body or '')[:600],server=f'IMAP {profile.imap_host}:{profile.imap_port}',metadata={'mode':application.email_mode,'template':profile.template})
        return uid
    finally: im.logout()


class BeautifulText:
    @staticmethod
    def from_html(html):
        text=str(html or '')
        # Insert line breaks before stripping markup. Treat the block elements users can
        # create in ScoutBox as real text boundaries so paragraphs/lists never collapse.
        text=re.sub(r'(?i)<br\s*/?>','\n',text)
        text=re.sub(r'(?i)</(?:p|div|blockquote|h[1-6]|pre|tr)\s*>','\n\n',text)
        text=re.sub(r'(?i)<li(?:\s[^>]*)?>','- ',text)
        text=re.sub(r'(?i)</li\s*>','\n',text)
        text=re.sub(r'<[^>]+>','',text)
        text=bleach.clean(text,tags=[],strip=True)
        text=text.replace('\r\n','\n').replace('\r','\n')
        text=re.sub(r'[ \t]+\n','\n',text)
        text=re.sub(r'\n[ \t]+','\n',text)
        text=re.sub(r'\n{3,}','\n\n',text)
        return text.strip()


def delete_draft(application, reason='Deleted from application editor'):
    profile=active_profile(); days=PortalSettings.objects.get_or_create(pk=1)[0].draft_suppression_days
    im=connect(profile)
    try:
        folder=application.imap_draft_folder or profile.drafts_folder or 'Drafts'; ensure_folder(im,folder)
        uids=[]
        if application.imap_draft_uid: uids.append(application.imap_draft_uid)
        if application.imap_message_id: uids += _uids_for_header(im,folder,'Message-ID',application.imap_message_id)
        for uid in set(uids): _delete_uid(im,uid)
        MailEvent.objects.create(kind='draft_delete',application=application,subject=application.email_subject,recipients=application.opportunity.contact_email,folder=folder,uid=application.imap_draft_uid,body_excerpt=reason[:600],server=f'IMAP {profile.imap_host}:{profile.imap_port}',metadata={'template':profile.template})
        application.imap_draft_uid=''; application.status='suppressed'; application.draft_suppression_reason=reason; application.draft_suppressed_until=timezone.now()+timezone.timedelta(days=days); application.save()
    finally: im.logout()


def decode_value(v):
    try: return str(make_header(decode_header(v or '')))
    except Exception: return v or ''


def body_text(msg):
    parts=[]
    if msg.is_multipart():
        for p in msg.walk():
            if p.get_content_type()=='text/plain' and 'attachment' not in (p.get('Content-Disposition') or ''):
                try: parts.append(p.get_payload(decode=True).decode(p.get_content_charset() or 'utf-8',errors='replace'))
                except Exception: pass
    else:
        try: parts.append(msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8',errors='replace'))
        except Exception: pass
    return '\n'.join(parts)


def forwarded_headers(text):
    """Return embedded original-message headers, preferring the last forwarded block."""
    blocks=[]; current={}
    for line in (text or '').splitlines():
        if any(m.lower() in line.lower() for m in FORWARD_MARKERS):
            if current: blocks.append(current); current={}
            continue
        m=FORWARDED_HEADER_RE.match(line)
        if m: current[m.group(1).lower()]=m.group(2).strip()
        elif current and line.strip()=='' :
            blocks.append(current); current={}
    if current: blocks.append(current)
    return blocks[-1] if blocks else {}


def original_sender_from_body(text):
    h=forwarded_headers(text); raw=h.get('from','')
    addrs=getaddresses([raw]);
    if addrs and addrs[-1][1]: return addrs[-1][0].strip(),addrs[-1][1].lower()
    # fallback for loosely formatted forwarded messages
    matches=re.findall(r'(?im)^\s*From\s*:\s*(.+)$',text or '')
    for raw in reversed(matches):
        a=getaddresses([raw])
        if a and a[-1][1]: return a[-1][0].strip(),a[-1][1].lower()
    return '',''


def clean_contact_text(value, limit=500):
    """Decode presentation/extraction artifacts in plain-text contact fields only."""
    text=html_lib.unescape(str(value or ''))
    # Extractors sometimes leave one or two layers of URL encoding in plain text.
    for _ in range(2):
        decoded=unquote(text)
        if decoded==text:
            break
        text=decoded
    text=re.sub(r'[\x00-\x1f\x7f]+',' ',text)
    text=' '.join(text.split()).strip()
    return text[:max(1,int(limit or 500))]


def clean_contact_email(value):
    """Return a normalized email value without HTML/URL encoding artifacts."""
    raw=clean_contact_text(value,400).strip()
    if raw.lower().startswith('mailto:'):
        raw=raw[7:]
    raw=raw.split('?',1)[0].strip().strip("<>\"' ,;:")
    raw=re.sub(r'\s+','',raw)
    return raw.lower()[:254]


def is_non_contact_address(addr):
    """Administrative/policy/accommodation mailboxes are never auto-selected as contacts."""
    raw=clean_contact_email(addr)
    if raw in KNOWN_NON_CONTACT_EMAILS or raw == 'idisability.administrator@emerson.com':
        return True
    local=(raw.split('@',1)[0] if '@' in raw else raw)
    compact=re.sub(r'[^a-z0-9]+','',local)
    return any(re.sub(r'[^a-z0-9]+','',marker) in compact for marker in NON_CONTACT_MARKERS)


def contact_email_has_non_contact_context(addr, text):
    """Return True when an email is presented as an accommodation/accessibility route.

    The mailbox name alone is often ambiguous (for example TAOps@marvell.com), so inspect
    only a small evidence window around the exact address. This preserves the source text
    while preventing policy/helpdesk addresses from becoming application contacts.
    """
    raw=clean_contact_email(addr)
    blob=str(text or '')
    if not raw or not blob:
        return False
    lower=blob.casefold()
    needle=raw.casefold()
    start=0
    while True:
        pos=lower.find(needle,start)
        if pos < 0:
            break
        window=lower[max(0,pos-360):min(len(lower),pos+len(needle)+360)]
        normalized=' '.join(window.replace('\n',' ').replace('\r',' ').split())
        if any(phrase in normalized for phrase in NON_CONTACT_CONTEXT_PHRASES):
            return True
        start=pos+len(needle)
    return False


def assignable_contact_email(addr, context=''):
    """Automatic contact-assignment guardrail, including surrounding page context."""
    raw=clean_contact_email(addr)
    return bool(raw and '@' in raw and not is_non_contact_address(raw) and not contact_email_has_non_contact_context(raw,context))


def is_generic(addr):
    """Return True for shared/functional mailboxes, including dotted variants.

    Earlier releases removed dots before checking the generic local-part list, so an
    address such as help.join@example.com became ``helpjoin`` and slipped through as a
    person-looking mailbox.  Treat separators as token boundaries instead: help.join,
    careers.sg and contact-team are all functional addresses (regional routes remain a
    separate, explicit exception in automatic_addressbook_contact_allowed()).
    """
    addr=clean_contact_email(addr)
    if is_non_contact_address(addr): return True
    raw_local=(addr.split('@',1)[0] if '@' in addr else addr).lower().split('+',1)[0]
    compact=re.sub(r'[^a-z0-9]+','',raw_local)
    if any(x in compact for x in ('noreply','donotreply','mailerdaemon')): return True
    if 'sales' in compact: return True
    tokens=[x for x in re.split(r'[._-]+',raw_local) if x]
    if any(token in GENERIC_LOCALPARTS for token in tokens): return True
    normalized='-'.join(tokens)
    return normalized in GENERIC_LOCALPARTS or any(normalized.startswith(x+'-') for x in GENERIC_LOCALPARTS)


# Region-specific routing mailboxes are useful enough for automated Address Book
# collection even when no named person is exposed. They represent a concrete regional
# contact route rather than a generic department inbox such as info@ or sales@.
REGION_ROUTING_LOCALPARTS={
    'singapore','sg','apac','asia','sea','southeastasia','emea','europe','eu','uk','unitedkingdom',
    'usa','us','unitedstates','canada','ca','australia','au','anz','newzealand','nz','india',
    'japan','jp','korea','kr','china','cn','hongkong','hk','taiwan','tw','malaysia','my',
    'indonesia','id','thailand','th','vietnam','vn','philippines','ph','mexico','mx','brazil','br','latam',
    'germany','de','france','fr','spain','es','italy','it','netherlands','nl','sweden','se','norway','no',
}


def is_region_routing_address(addr):
    raw=clean_contact_email(addr)
    local=raw.split('@',1)[0].split('+',1)[0] if '@' in raw else raw
    compact=re.sub(r'[^a-z0-9]+','',local)
    if compact in REGION_ROUTING_LOCALPARTS:
        return True
    # Accept obvious regional routes such as careers-singapore@ only when the region
    # token is explicit. This exception is deliberately narrow.
    tokens=[re.sub(r'[^a-z0-9]+','',x) for x in re.split(r'[._-]+',local) if x]
    return any(t in REGION_ROUTING_LOCALPARTS and len(t)>=2 for t in tokens)


def automatic_addressbook_contact_allowed(addr, name=''):
    """Fail closed for automatic Address Book collection.

    Automatic ingestion keeps a named/human-looking mailbox or a concrete regional
    route. Generic functional inboxes (info@, contact@, jobs@, sales@, support@, etc.)
    stay available on Opportunity/Lead records but do not accumulate in Address Book.
    Manual Address Book entries are intentionally unaffected.
    """
    raw=clean_contact_email(addr)
    if not raw or '@' not in raw or is_non_contact_address(raw):
        return False
    if is_region_routing_address(raw):
        return True
    if is_generic(raw):
        return False
    derived=contact_name_from_email(raw)
    supplied=' '.join(str(name or '').split()).strip()
    if supplied and supplied.casefold() not in {'contact','unknown','n/a','none','team','support','sales','recruiting','hr'}:
        return True
    return bool(derived)

def contact_company_from_email(addr):
    addr=clean_contact_email(addr)
    domain=(addr.split('@',1)[1] if '@' in addr else '').lower().split(':',1)[0]
    labels=[x for x in domain.split('.') if x and x not in ('www','mail','email','smtp')]
    if not labels: return ''
    common={'gmail','googlemail','outlook','hotmail','yahoo','icloud','protonmail','proton','live','msn','aol','gmx'}
    if labels[0] in common: return ''
    return labels[0].replace('-',' ').replace('_',' ').title()[:200]


def contact_name_from_email(addr):
    """Best-effort salutation-grade name from an email username.

    This is Address Book presentation logic, not discovery filtering.  A clear
    separator is strong evidence (rachel.weiss -> Rachel Weiss, alex.m -> Alex M),
    while obvious shared/admin mailboxes stay nameless.
    """
    raw=clean_contact_email(addr)
    if not raw or is_generic(raw.lower()) or is_non_contact_address(raw.lower()): return ''
    local=raw.split('@',1)[0].split('+',1)[0].strip()
    if not local: return ''
    local=re.sub(r'([a-z])([A-Z])',r'\1 \2',local)
    local=re.sub(r'[._-]+',' ',local)
    local=re.sub(r'\d+',' ',local)
    words=[w for w in re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ']+",local) if w]
    if not words: return ''
    generic_words={'team','jobs','job','career','careers','support','sales','info','hello','contact','admin','office','recruiting','recruitment','talent','hr','billing','service'}
    if any(w.lower() in generic_words for w in words): return ''
    if len(words)==1 and any(words[0].lower().endswith(suffix) for suffix in ('jobs','careers','recruiting','recruitment','talent','support','contact')): return ''
    if len(words)==1 and len(words[0])<3: return ''
    return ' '.join((w.upper() if len(w)==1 else w.capitalize()) for w in words[:4])[:200]



_AUTO_CONTACT_EMAIL_RE=re.compile(r'(?i)(?<![A-Z0-9._%+\-])([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})(?![A-Z0-9._%+\-])')
_AUTO_CONTACT_PUBLIC_SUFFIX_2={'co.uk','org.uk','ac.uk','com.au','net.au','org.au','co.nz','com.sg','com.my','co.jp','co.kr','ac.kr','co.in','com.br','com.cn','com.tw','edu.sg'}
_AUTO_CONTACT_FREE_MAIL={'gmail.com','googlemail.com','outlook.com','hotmail.com','yahoo.com','icloud.com','protonmail.com','proton.me','live.com','msn.com','aol.com','gmx.com'}

_AUTO_CONTACT_THIRD_PARTY_HOSTS={
    'linkedin.com','indeed.com','glassdoor.com','github.com','gitlab.com','bitbucket.org','wellfound.com',
    'ziprecruiter.com','simplyhired.com','monster.com','seek.com','jobsdb.com','findjob24h.com','reddit.com',
}
_AUTO_CONTACT_HOST_LABELS={
    'linkedin','indeed','glassdoor','github','gitlab','bitbucket','wellfound','ziprecruiter','simplyhired',
    'monster','seek','jobsdb','findjob24h','reddit','ac','snu',
}


def _addressbook_company_is_host_label(company='', source_url=''):
    """Return True only when the stored company still looks like the page host."""
    company_slug=_addressbook_company_slug(company)
    source_domain=_addressbook_registrable_domain(source_url)
    source_slug=_addressbook_domain_slug(source_domain)
    if not company_slug:
        return True
    if company_slug in _AUTO_CONTACT_HOST_LABELS:
        return True
    if source_domain in _AUTO_CONTACT_THIRD_PARTY_HOSTS:
        return company_slug==source_slug
    # University/community boards can host roles for outside employers. Only treat a
    # short/domain-shaped label as the host; a real university name remains authoritative.
    academic=source_domain.endswith('.edu') or '.ac.' in source_domain or source_domain.endswith('.ac.kr')
    return bool(academic and (company_slug==source_slug or len(company_slug)<=4))


def employer_from_contact_evidence(addr, evidence='', company='', source_url=''):
    """Recover an employer only from strong retained page evidence.

    The email domain alone is not enough: external recruiters are legitimate. For a
    third-party-hosted record, the domain-derived organization must also be named in the
    retained page text outside the email/domain itself. This lets ``emily@pillpresso.com``
    repair a GitHub-hosted Pillpresso posting without letting an arbitrary recruiter
    mailbox redefine a direct-employer posting.
    """
    raw=clean_contact_email(addr)
    if not raw or '@' not in raw or is_non_contact_address(raw):
        return ''
    if not _addressbook_company_is_host_label(company,source_url):
        return ''
    email_domain=_addressbook_registrable_domain(raw)
    source_domain=_addressbook_registrable_domain(source_url)
    if not email_domain or email_domain in _AUTO_CONTACT_FREE_MAIL or email_domain==source_domain:
        return ''
    candidate=contact_company_from_email(raw)
    candidate_slug=_addressbook_company_slug(candidate)
    if len(candidate_slug)<5:
        return ''
    if isinstance(evidence,(list,tuple,set)):
        blob='\n'.join(str(x or '') for x in evidence)
    else:
        blob=str(evidence or '')
    if not blob:
        return ''
    # Remove the mailbox and bare domain before looking for the organization name. This
    # prevents the address itself from being mistaken for independent employer evidence.
    scrubbed=re.sub(re.escape(raw),' ',blob,flags=re.I)
    scrubbed=re.sub(re.escape(email_domain),' ',scrubbed,flags=re.I)
    normalized=re.sub(r'[^a-z0-9]+','',scrubbed.casefold())
    return candidate[:200] if candidate_slug in normalized else ''


def _addressbook_material_state(contact):
    """Snapshot contact fields whose change is meaningful enough for Audit Trail."""
    if contact is None:
        return None
    return {
        'name':str(getattr(contact,'name','') or ''),
        'company':str(getattr(contact,'company','') or ''),
        'title':str(getattr(contact,'title','') or ''),
        'phone':str(getattr(contact,'phone','') or ''),
        'source':str(getattr(contact,'source','') or ''),
        'source_url':str(getattr(contact,'source_url','') or ''),
        'generic':bool(getattr(contact,'generic',False)),
        'confidence':int(getattr(contact,'confidence',0) or 0),
        'notes':str(getattr(contact,'notes','') or ''),
        'company_summary':str(getattr(contact,'company_summary','') or ''),
        'company_country':str(getattr(contact,'company_country','') or ''),
        'company_intel':copy.deepcopy(getattr(contact,'company_intel',{}) or {}),
    }


def _log_addressbook_promotion(outcome, *, email='', company='', source='', source_url='', record=None, reason=''):
    """0.10.94: routine Address Book promotion is operational provenance, not audit.

    Kept as a compatibility no-op for older call sites. Material provenance is persisted
    on the Contact itself once a Contact exists.
    """
    return None


def _store_addressbook_provenance(contact, *, source='', source_url='', record=None):
    if contact is None:
        return
    try:
        ctx=usage_context() or {}
        provenance=dict(getattr(contact,'origin_provenance',{}) or {})
        provenance.update({
            'campaign_id':ctx.get('campaign_id') or provenance.get('campaign_id'),
            'campaign_run_id':ctx.get('campaign_run_id') or provenance.get('campaign_run_id'),
            'source':str(source or provenance.get('source') or '')[:120],
            'source_url':str(source_url or provenance.get('source_url') or '')[:1000],
            'record_type':record.__class__.__name__ if record is not None else provenance.get('record_type',''),
            'record_id':str(getattr(record,'pk','') or '') if record is not None else provenance.get('record_id',''),
            'promoted_at':timezone.now().isoformat(),
        })
        contact.origin_provenance=provenance
        contact.save(update_fields=['origin_provenance'])
    except Exception:
        pass


def _addressbook_registrable_domain(value):
    """Small dependency-free registrable-domain helper for contact ownership checks."""
    raw=str(value or '').strip().lower()
    if '@' in raw and '://' not in raw:
        raw=raw.rsplit('@',1)[-1]
    if '://' not in raw:
        raw='https://'+raw
    try:
        from urllib.parse import urlsplit
        host=(urlsplit(raw).hostname or '').lower().removeprefix('www.')
    except Exception:
        return ''
    labels=[x for x in host.split('.') if x]
    if len(labels)<2: return host
    tail='.'.join(labels[-2:])
    if tail in _AUTO_CONTACT_PUBLIC_SUFFIX_2 and len(labels)>=3:
        return '.'.join(labels[-3:])
    return tail


def _addressbook_company_slug(value):
    text=' '.join(str(value or '').split()).casefold()
    text=re.sub(r'\b(?:incorporated|inc|llc|ltd|limited|gmbh|ag|plc|corp|corporation|company|co|pte)\b\.?',' ',text)
    return re.sub(r'[^a-z0-9]+','',text)


def _addressbook_domain_slug(domain):
    reg=_addressbook_registrable_domain(domain)
    if not reg: return ''
    labels=reg.split('.')
    label=labels[0] if len(labels)>=2 else reg
    return re.sub(r'[^a-z0-9]+','',label.casefold())


def contact_ownership_plausible(addr, company='', source_url='', evidence=''):
    """Conservative deterministic ownership gate for discovered public contacts.

    Direct domain/company matches remain the default. A narrow third-party-host exception
    is allowed only when retained page evidence independently names the organization
    implied by the email domain. This preserves the TAOps-style contamination guard while
    allowing legitimate employer mailboxes on GitHub, university and job-board pages.
    """
    raw=clean_contact_email(addr)
    if not raw or '@' not in raw: return False
    email_domain=_addressbook_registrable_domain(raw)
    if not email_domain or email_domain in _AUTO_CONTACT_FREE_MAIL: return False
    source_domain=_addressbook_registrable_domain(source_url)
    if source_domain and source_domain==email_domain:
        return True
    company_slug=_addressbook_company_slug(company)
    domain_slug=_addressbook_domain_slug(email_domain)
    if company_slug and domain_slug:
        if company_slug==domain_slug:
            return True
        # Brand/domain punctuation and compact suffixes are common (BEC Systems ->
        # bec-systems.com). Require a useful length before accepting containment so short
        # acronyms do not match unrelated organizations by accident.
        if min(len(company_slug),len(domain_slug))>=5 and (company_slug in domain_slug or domain_slug in company_slug):
            return True
    return bool(employer_from_contact_evidence(raw,evidence,company,source_url))


def find_automatic_contact_email(texts, company='', source_url=''):
    """Find the best auto-promotable public email from already-retained page text."""
    candidates=[]
    seen=set()
    for text in texts or []:
        for match in _AUTO_CONTACT_EMAIL_RE.findall(str(text or '')):
            email=clean_contact_email(match)
            if not email or email in seen:
                continue
            seen.add(email)
            if contact_email_has_non_contact_context(email,text):
                continue
            if not automatic_addressbook_contact_allowed(email):
                continue
            if not contact_ownership_plausible(email,company,source_url,text):
                continue
            name=contact_name_from_email(email)
            same_domain=_addressbook_registrable_domain(email)==_addressbook_registrable_domain(source_url)
            score=(3 if name else 1)+(2 if same_domain else 0)
            candidates.append((score,email))
    candidates.sort(key=lambda x:(-x[0],x[1]))
    return candidates[0][1] if candidates else ''



def _addressbook_contact_has_fit(contact):
    try:
        intel=dict(getattr(contact,'company_intel',{}) or {})
        fit=intel.get('fit_classification') if isinstance(intel.get('fit_classification'),dict) else {}
        return ('score' in fit and fit.get('score') not in (None,''))
    except Exception:
        return False


def _addressbook_related_fit(contact):
    """Return a bounded inherited Fit score from the record that produced a contact.

    Address Book entries are often created after an Opportunity or Hidden Lead already
    earned a useful Fit score. Reusing that score is better than leaving a permanent '?',
    but it is explicitly labelled as inherited rather than pretending the contact itself
    has been independently reviewed.
    """
    try:
        email=clean_contact_email(getattr(contact,'email','') or '')
        company=' '.join(str(getattr(contact,'company','') or '').split()).strip()
        source_url=str(getattr(contact,'source_url','') or '').strip()
        q=Q()
        if email:
            q |= Q(contact_email__iexact=email)
        if source_url:
            q |= Q(url__iexact=source_url) | Q(target_url__iexact=source_url) | Q(search_url__iexact=source_url) | Q(canonical_url__iexact=source_url)
        if company and len(company)>=3:
            q |= Q(company__iexact=company)
        if q:
            opp=Opportunity.objects.filter(q,user_deleted=False,suppressed=False).exclude(status='rejected').order_by('-fit_score','-last_seen').first()
            if opp and int(getattr(opp,'fit_score',0) or 0)>0:
                return max(0,min(100,int(opp.fit_score or 0))), 'originating Opportunity', getattr(opp,'pk',None)
        q=Q()
        if email:
            q |= Q(contact_email__iexact=email)
        if source_url:
            q |= Q(target_url__iexact=source_url) | Q(source_url__iexact=source_url) | Q(search_url__iexact=source_url)
        if company and len(company)>=3:
            q |= Q(company__iexact=company)
        if q:
            lead=CompanyLead.objects.filter(q,user_deleted=False,deleted_at__isnull=True).order_by('-score','-updated_at').first()
            if lead and int(getattr(lead,'score',0) or 0)>0:
                return max(0,min(100,int(lead.score or 0))), 'originating Hidden Lead', getattr(lead,'pk',None)
    except Exception:
        pass
    return None, '', None


def _addressbook_heuristic_fit_score(contact):
    """Low-confidence deterministic fallback for automatic Address Book rows.

    This prevents auto-discovered contacts with enough evidence from showing '?' forever
    when the configured AI route is unavailable. Manual contacts without discovery
    provenance are deliberately left unscored unless they have meaningful company/source
    evidence.
    """
    try:
        intel=dict(getattr(contact,'company_intel',{}) or {})
    except Exception:
        intel={}
    company=' '.join(str(getattr(contact,'company','') or '').split()).strip()
    source_url=str(getattr(contact,'source_url','') or '').strip()
    summary=' '.join(str(getattr(contact,'company_summary','') or '').split()).strip()
    title=' '.join(str(getattr(contact,'title','') or '').split()).strip()
    notes=' '.join(str(getattr(contact,'notes','') or '').split()).strip()
    source=' '.join(str(getattr(contact,'source','') or '').split()).strip().casefold()
    manual=(source=='manual')
    evidence_count=sum(1 for value in (company,source_url,summary,title,notes) if value)
    has_company_intel=False
    if isinstance(intel,dict):
        for key in ('employee_count','employee_range','company_size_label','founded_year','domain_registered_at','domain_age_years','industry','website','country'):
            if intel.get(key) not in (None,'',[],{}):
                has_company_intel=True; break
    if manual and evidence_count < 2 and not has_company_intel:
        return None, 0, 'Manual Address Book contact has not been Fit-assessed yet.'
    score=40
    if company: score+=8
    if title: score+=6
    if source_url: score+=6
    if summary: score+=8
    if has_company_intel: score+=8
    if notes: score+=4
    try:
        confidence=int(getattr(contact,'confidence',0) or 0)
    except Exception:
        confidence=0
    if confidence>=80: score+=5
    elif confidence<50: score-=5
    return max(25,min(70,score)), (35 if not manual else 25), 'Deterministic fallback from Address Book company/contact evidence; direct AI Fit assessment was unavailable or inconclusive.'


def ensure_addressbook_contact_fit(contact, *, reason=''):
    """Ensure an Address Book contact has a displayable Fit score when evidence allows.

    Order of preference: existing direct score, inherited Opportunity/Hidden Lead score,
    then low-confidence deterministic fallback for evidence-backed contacts. This helper
    is network-free and safe in migrations, mailbox ingestion and company research jobs.
    """
    try:
        intel=dict(getattr(contact,'company_intel',{}) or {})
    except Exception:
        intel={}
    fit=intel.get('fit_classification') if isinstance(intel.get('fit_classification'),dict) else {}
    if isinstance(fit,dict) and fit.get('score') not in (None,''):
        return True, fit
    inherited_score, inherited_source, inherited_id = _addressbook_related_fit(contact)
    now=timezone.now().isoformat()
    if inherited_score is not None:
        intel['fit_classification']={
            'score':int(inherited_score),'confidence':55,
            'reason':f'Inherited from the {inherited_source} that produced or matches this Address Book entry.',
            'source':'Address Book inherited Fit fallback','origin':inherited_source,
            'origin_id':inherited_id,'at':now,
        }
        intel['inherited_fit']={
            'score':int(inherited_score),'source':inherited_source,'origin_id':inherited_id,
            'reason':'Temporary fallback until direct Address Book Fit assessment succeeds.','at':now,
        }
        contact.company_intel=intel
        return True, intel['fit_classification']
    fallback_score, confidence, fallback_reason = _addressbook_heuristic_fit_score(contact)
    if fallback_score is not None:
        intel['fit_classification']={
            'score':int(fallback_score),'confidence':int(confidence),
            'reason':fallback_reason,
            'source':'Address Book deterministic fallback','provider':'deterministic','model':'addressbook-v1',
            'at':now,
        }
        if reason:
            intel['fit_assessment_error']=str(reason)[:300]
        contact.company_intel=intel
        return True, intel['fit_classification']
    if reason:
        intel['fit_assessment_error']=str(reason)[:300]
        contact.company_intel=intel
    return False, {}

def assess_addressbook_contact_fit(contact):
    """Assess Address Book Fit before/after persistence using the configured route.

    Direct AI assessment remains preferred. When the AI route is unavailable, empty, or
    inconclusive, use an explicitly labelled inherited/deterministic fallback so
    evidence-backed Address Book rows do not show '?' forever.
    """
    try:
        intel=dict(getattr(contact,'company_intel',{}) or {})
    except Exception:
        intel={}
    current=intel.get('fit_classification') if isinstance(intel.get('fit_classification'),dict) else {}
    try:
        if 'score' in current and current.get('score') not in (None,''):
            score=max(0,min(100,int(current.get('score'))))
            return True,current
    except Exception:
        pass
    try:
        from .ai import effective_route_for_stage
        from .opportunity_filter import classify_existing_contact
        ps=PortalSettings.objects.get_or_create(pk=1)[0]
        mode=str(ps.discovery_mode or 'source_guided').strip().lower()
        route=dict(effective_route_for_stage('first_filter',discovery_mode=mode) or {})
        provider=str(route.get('provider') or '').strip().lower()
        model=str(route.get('model') or '').strip()
        if not provider or not model:
            return ensure_addressbook_contact_fit(contact, reason='No usable AI route/model for Address Book Fit assessment.')
        review=classify_existing_contact(
            contact,provider=provider,model=model,
            internet_search=(mode=='cloud_web' and provider in {'openai','gemini','openrouter'}),
            empty_response_budget=2,budget_operation='discovery',
        )
        raw=review.get('fit_score')
        if raw in (None,''):
            return ensure_addressbook_contact_fit(contact, reason=str(review.get('fit_reason') or 'AI Fit assessment returned no score.')[:300])
        score=max(0,min(100,int(raw)))
        intel=dict(getattr(contact,'company_intel',{}) or {})
        intel['fit_classification']={
            'score':score,'confidence':max(0,min(100,int(review.get('fit_confidence') or 0))),
            'reason':str(review.get('fit_reason') or '')[:1600],
            'source':'Pre-persistence Address Book fit assessment','provider':provider,'model':model,
            'at':timezone.now().isoformat(),
        }
        intel.setdefault('discovery_origin',{
            'mode':'cloud' if provider in {'openai','gemini','openrouter'} else 'local',
            'provider':provider,'model':model,'source':'Address Book pre-persistence fit',
            'at':timezone.now().isoformat(),
        })
        contact.company_intel=intel
        return True,review
    except Exception as exc:
        return ensure_addressbook_contact_fit(contact, reason=str(exc)[:300])


def broad_shared_contact_allowed(addr):
    """Useful organization routes permitted only by Broad Contact admission."""
    raw=clean_contact_email(addr)
    if not raw or '@' not in raw or is_non_contact_address(raw):
        return False
    local=raw.split('@',1)[0].split('+',1)[0].casefold()
    tokens={x for x in re.split(r'[._-]+',local) if x}
    useful={'jobs','careers','recruiting','recruitment','talent','engineering','engineers','research','partnerships','businessdevelopment','projects','consulting'}
    return bool(tokens & useful) or is_region_routing_address(raw)


def maybe_persist_addressbook_contact(email, *, name='', company='', source='', source_url='', confidence=75,
                                      notes='', company_summary='', company_country='', company_intel=None,
                                      require_company_match=True, queue_research=False, evidence_text='', record=None,
                                      apply_selectivity=True):
    """Create/update one active Address Book contact without resurrecting tombstones.

    Automatic ingestion is deliberately conservative. Functional/policy mailboxes stay
    available on Opportunities/Hidden Leads but are not promoted. A Contact explicitly
    moved to the Recycle Bin is a tombstone and is never touched or recreated.

    Returns ``(contact_or_none, created, outcome)`` where outcome is one of created,
    updated, unchanged, recycled, generic_or_invalid, ownership_mismatch, or selectivity_rejected.
    """
    raw=clean_contact_email(email)
    if not re.fullmatch(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}',raw or ''):
        _log_addressbook_promotion('generic_or_invalid',email=raw,company=company,source=source,source_url=source_url,record=record)
        return None,False,'generic_or_invalid'
    if is_non_contact_address(raw) or contact_email_has_non_contact_context(raw,evidence_text):
        _log_addressbook_promotion('non_contact_context',email=raw,company=company,source=source,source_url=source_url,record=record)
        return None,False,'non_contact_context'
    contact_level=selectivity_current('address_book') if apply_selectivity else 'balanced'
    contact_rules=contact_policy(contact_level)
    try: contact_confidence=max(0,min(100,int(confidence or 0)))
    except Exception: contact_confidence=0
    standard_allowed=automatic_addressbook_contact_allowed(raw,name)
    if not standard_allowed and not (contact_rules.get('allow_useful_shared') and broad_shared_contact_allowed(raw)):
        _log_addressbook_promotion('generic_or_invalid',email=raw,company=company,source=source,source_url=source_url,record=record)
        return None,False,'generic_or_invalid'
    if contact_confidence < int(contact_rules.get('minimum_confidence') or 0):
        _log_addressbook_promotion('selectivity_rejected',email=raw,company=company,source=source,source_url=source_url,record=record)
        return None,False,'selectivity_rejected'
    if require_company_match and not contact_ownership_plausible(raw,company,source_url,evidence_text):
        _log_addressbook_promotion('ownership_mismatch',email=raw,company=company,source=source,source_url=source_url,record=record)
        return None,False,'ownership_mismatch'
    if contact_rules.get('require_verified_person') and not contact_identity_verified(raw,name,evidence_text,contact_confidence):
        _log_addressbook_promotion('selectivity_rejected',email=raw,company=company,source=source,source_url=source_url,record=record)
        return None,False,'selectivity_rejected'

    existing=Contact.objects.filter(email__iexact=raw).first()
    if existing is not None and existing.deleted_at is not None:
        _log_addressbook_promotion('recycled',email=raw,company=company,source=source,source_url=source_url,record=record)
        return None,False,'recycled'

    fallback_company=' '.join(str(company or contact_company_from_email(raw)).split()).strip()[:200]
    if contact_level=='verified':
        cleaned_name=' '.join(str(name or '').split()).strip()[:200]
    elif not standard_allowed and contact_rules.get('allow_useful_shared'):
        cleaned_name=''
    else:
        cleaned_name=' '.join(str(name or contact_name_from_email(raw)).split()).strip()[:200]
    intel=company_intel if isinstance(company_intel,dict) else {}
    summary=' '.join(str(company_summary or '').split()).strip()[:2000]
    if not summary or not intel:
        stored_summary,stored_intel=_stored_company_context(fallback_company,raw,source_url)
        if not summary: summary=str(stored_summary or '')[:2000]
        if not intel and isinstance(stored_intel,dict): intel=stored_intel
    if not summary and intel:
        try: summary=company_summary_from_intel(intel,1200)[:2000]
        except Exception: pass

    before_state=_addressbook_material_state(existing)
    now=timezone.now()
    if existing is None:
        contact=Contact(
            email=raw,name=cleaned_name,company=fallback_company,source=str(source or 'Automatic discovery')[:120],
            source_url=str(source_url or '')[:1000],generic=False,confidence=max(0,min(100,int(confidence or 0))),
            notes=str(notes or '')[:2000],company_summary=summary,company_country=str(company_country or '')[:120],
            company_intel=intel,last_seen=now,is_read=False,
        )
        # New automatic Address Book rows are Fit-assessed before their first INSERT.
        assess_addressbook_contact_fit(contact)
        contact.save()
        created=True
    else:
        contact=existing; created=False; changed=[]
        auto_owned=str(contact.source or '').lower() not in {'manual'}
        def assign_if_changed(field,value,allowed=True):
            if not allowed:
                return
            if getattr(contact,field) != value:
                setattr(contact,field,value); changed.append(field)
        assign_if_changed('name',cleaned_name,bool(cleaned_name) and (not contact.name or auto_owned))
        assign_if_changed('company',fallback_company,bool(fallback_company) and (not contact.company or auto_owned))
        assign_if_changed('source_url',str(source_url)[:1000],bool(source_url) and (not contact.source_url or auto_owned))
        assign_if_changed('source',str(source)[:120],bool(source) and auto_owned)
        assign_if_changed('company_summary',summary,bool(summary) and (not contact.company_summary or auto_owned))
        assign_if_changed('company_country',str(company_country)[:120],bool(company_country) and (not contact.company_country or auto_owned))
        assign_if_changed('company_intel',intel,bool(intel) and (not contact.company_intel or auto_owned))
        assign_if_changed('notes',str(notes)[:2000],bool(notes) and auto_owned)
        assign_if_changed('generic',False,contact.generic is not False)
        new_confidence=max(int(contact.confidence or 0),max(0,min(100,int(confidence or 0))))
        assign_if_changed('confidence',new_confidence)
        # last_seen is intentionally persisted on rediscovery but excluded from material
        # state, so a timestamp-only refresh never produces an Audit Trail entry.
        contact.last_seen=now
        contact.save(update_fields=list(dict.fromkeys(changed+['last_seen'])))

    # Reuse retained company evidence immediately. Optional network/AI research is only
    # queued by callers that already used this behaviour (mailbox ingestion); discovery
    # itself must not unexpectedly increase cloud consumption.
    try:
        enrich_company_intel_from_retained(contact)
    except Exception:
        pass
    # Existing/rediscovered contacts may pre-date Fit assessment. Reuse their retained
    # company evidence and assess only when no valid classification exists.
    try:
        current_intel=dict(contact.company_intel or {})
        current_fit=current_intel.get('fit_classification') if isinstance(current_intel.get('fit_classification'),dict) else {}
        if not ('score' in current_fit and current_fit.get('score') not in (None,'')):
            assessed,_review=assess_addressbook_contact_fit(contact)
            if assessed:
                contact.save(update_fields=['company_intel'])
    except Exception:
        pass
    if queue_research:
        try:
            if not company_info_has_display_data(contact):
                from celery import current_app
                from portal.models import BackgroundJob
                active=BackgroundJob.objects.filter(kind='company_research',status__in=['queued','running'],result__contact_id=contact.pk).first()
                if not active:
                    job=BackgroundJob.objects.create(kind='company_research',label=f'Address Book company research: {contact.company or contact.email}'[:300],message='Queued',result={'contact_id':contact.pk,'address_book':True,'phase':'initial'})
                    task=current_app.send_task('portal.tasks.contact_company_research_job',args=[job.pk,contact.pk,'initial'])
                    job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
        except Exception:
            pass
    after_state=_addressbook_material_state(contact)
    outcome='created' if created else ('updated' if before_state != after_state else 'unchanged')
    if outcome in {'created','updated'}:
        _store_addressbook_provenance(contact,source=source,source_url=source_url,record=record)
    return contact,created,outcome



def _company_focused_summary_from_record(record, texts=()):
    """Build a concise Address Book summary from already-retained company evidence.

    Opportunity rows do not have the Hidden Lead ``summary`` field.  Prefer structured
    Company Info, then a company-focused sentence from retained evidence.  Role duties
    are deliberately not copied merely to avoid an empty Address Book cell.
    """
    intel=getattr(record,'company_intel',{}) if isinstance(getattr(record,'company_intel',{}),dict) else {}
    summary=company_summary_from_intel(intel,1200) if intel else ''
    if summary:
        return ' '.join(summary.split())[:2000]
    direct=' '.join(str(getattr(record,'summary','') or '').split()).strip() if hasattr(record,'summary') else ''
    if direct:
        return direct[:2000]
    company=' '.join(str(getattr(record,'company','') or '').split()).strip()
    try:
        stored,_stored_intel=stored_company_context(company,getattr(record,'contact_email','') or '',getattr(record,'target_url','') or getattr(record,'source_url','') or getattr(record,'url','') or '')
        if stored:
            return ' '.join(str(stored).split())[:2000]
    except Exception:
        pass
    candidates=[]
    for field in ('raw_search_snippet','recommendation_reason','list_highlight','description','evidence','match_summary'):
        value=str(getattr(record,field,'') or '').strip()
        if value:
            candidates.append(value)
    candidates.extend(str(x or '').strip() for x in (texts or ()) if str(x or '').strip())
    text=' '.join(candidates)[:18000]
    if not text:
        return ''
    company_tokens=[x for x in re.findall(r'[a-z0-9]+',company.casefold()) if len(x)>=4 and x not in {'company','technologies','technology','solutions','systems','group','labs'}]
    org_verbs=('builds','develops','designs','manufactures','provides','offers','creates','makes','operates','specializes','specialises','platform','products','services','solutions','customers')
    role_noise=('responsibilities','requirements','candidate will','you will','the role','job description','years of experience','apply now')
    sentences=re.split(r'(?<=[.!?])\s+|\n+',re.sub(r'\s+',' ',text))
    ranked=[]
    for sentence in sentences:
        clean=' '.join(sentence.split()).strip(' -–—|')
        if len(clean)<25 or len(clean)>520:
            continue
        low=clean.casefold()
        if any(n in low for n in role_noise):
            continue
        company_hit=bool(company_tokens and any(t in low for t in company_tokens[:5]))
        org_hit=any(v in low for v in org_verbs)
        if not org_hit:
            continue
        ranked.append(((2 if company_hit else 0)+(1 if len(clean)<=260 else 0),clean))
    if not ranked:
        return ''
    ranked.sort(key=lambda x:x[0],reverse=True)
    return ranked[0][1][:2000]


def promote_record_contact_to_addressbook(record, *, source='Automatic discovery', source_url='', texts=(), confidence=75, queue_research=False):
    """Promote a safe contact from an Opportunity/Hidden Lead into Address Book.

    Third-party job/community hosts are not treated as employers when retained text
    independently names the organization that owns a discovered mailbox. The correction
    is deliberately evidence-bound: an email domain alone can never redefine a company.
    """
    values=tuple(texts or ())
    company=' '.join(str(getattr(record,'company','') or '').split()).strip()
    url=str(source_url or getattr(record,'target_url','') or getattr(record,'source_url','') or getattr(record,'canonical_url','') or getattr(record,'url','') or getattr(record,'search_url','') or '').strip()
    email=clean_contact_email(getattr(record,'contact_email','') or '')
    blocked_reason=''
    if email and (is_non_contact_address(email) or any(contact_email_has_non_contact_context(email,text) for text in values)):
        blocked_reason='non_contact_context'
        email=''
    if not email:
        email=find_automatic_contact_email(values,company,url)
    inferred=employer_from_contact_evidence(email,values,company,url) if email else ''
    changed=[]
    if inferred and _addressbook_company_is_host_label(company,url) and inferred.casefold()!=company.casefold():
        company=inferred
        if hasattr(record,'company'):
            record.company=inferred; changed.append('company')
    if email and clean_contact_email(getattr(record,'contact_email','') or '')!=email:
        setattr(record,'contact_email',email); changed.append('contact_email')
    if email and hasattr(record,'contact_name') and not str(getattr(record,'contact_name','') or '').strip():
        derived=contact_name_from_email(email)
        if derived:
            record.contact_name=derived; changed.append('contact_name')
    if changed:
        try:
            record.save(update_fields=list(dict.fromkeys(changed+['updated_at'])))
        except Exception:
            try: record.save(update_fields=list(dict.fromkeys(changed)))
            except Exception: pass
    if not email:
        _log_addressbook_promotion(blocked_reason or 'no_email',company=company,source=source,source_url=url,record=record)
        return None,False,(blocked_reason or 'no_email')
    name=str(getattr(record,'contact_name','') or '').strip()
    intel=getattr(record,'company_intel',{}) if isinstance(getattr(record,'company_intel',{}),dict) else {}
    summary=_company_focused_summary_from_record(record,values)
    country=str(getattr(record,'country','') or '')
    # Address Book's compact Country field should retain the posting's recruiter region
    # (EMEA/APAC/etc.) when the role page provides one. Older Jobicy structured data can
    # expand that same region into dozens of countries, which is both noisy and misleading.
    role_location=str(getattr(record,'role_location','') or '')
    role_items=parse_location_items(role_location,source='role_location',evidence=role_location) if role_location else []
    if role_items:
        country=legacy_location_text(role_items)
    return maybe_persist_addressbook_contact(
        email,name=name,company=company,source=source,source_url=url,confidence=confidence,
        company_summary=summary,company_country=country,company_intel=intel,
        require_company_match=True,queue_research=queue_research,evidence_text=values,record=record,
    )

def _stored_company_context(company='',email='',source_url=''):
    """Reuse strongest existing company research without network/AI work."""
    return stored_company_context(company,email,source_url)


def _stored_company_summary(company='',email=''):
    return _stored_company_context(company,email)[0]


def extract_human_contacts(msg,text,company=''):
    candidates=[]; fwd=original_sender_from_body(text)
    if fwd[1]: candidates.append((clean_contact_text(fwd[0],200),clean_contact_email(fwd[1]),'forwarded-body',92))
    for header,score in [('Reply-To',95),('From',90),('To',60),('Cc',55)]:
        for name,addr in getaddresses([msg.get(header,'')]):
            if addr: candidates.append((clean_contact_text(name,200),clean_contact_email(addr),header.lower(),score))
    for name,addr,source,score in candidates:
        if is_non_contact_address(addr): continue
        generic=is_generic(addr)
        if generic: continue
        fallback_company=company or contact_company_from_email(addr)
        company_summary,company_intel=_stored_company_context(fallback_company,addr)
        # A real mailbox correspondent is already strong contact evidence, so this path
        # does not require the sender domain to match the application company (external
        # recruiters are legitimate). The shared helper still enforces generic/policy
        # mailbox rules and, critically, never touches an exact Recycle Bin tombstone.
        maybe_persist_addressbook_contact(
            addr,name=name.strip()[:200],company=fallback_company,source=source,
            confidence=score,company_summary=company_summary,company_intel=company_intel,
            require_company_match=False,queue_research=True,apply_selectivity=False,
        )


def _classify(text,subject,folder_kind='inbox'):
    """Infer the application state from message content, not the IMAP folder alone."""
    t=(str(subject or '')+'\n'+str(text or '')).lower()
    # Strong outcome language wins even for forwarded copies sitting in Sent/Drafts.
    if re.search(r'not (?:moving|progressing|proceeding) forward|unfortunately.{0,100}(?:not|unable)|not selected|other candidates|not a fit|declin(?:e|ed)|reject(?:ed|ion)|position.{0,60}(?:filled|closed)',t,re.S):
        return 'rejected',95
    if re.search(r'we (?:are )?(?:pleased|delighted) to (?:offer|invite)|job offer|offer letter|would like to (?:offer|engage)|start date|selected for the (?:role|position)',t):
        return 'accepted',93
    if re.search(r'interview|schedule.{0,60}(?:call|meeting)|next (?:step|round)|meet with|technical discussion|assessment|onsite|screening call',t,re.S):
        return 'interview',88
    if re.search(r'thank you for (?:applying|your application)|application (?:has been )?(?:received|submitted)|successfully applied|application confirmation|we received your application',t):
        return 'applied',84
    if re.search(r'follow.?up|checking in|any update|following up',t):
        return 'reply',68
    if folder_kind=='draft': return 'draft',70
    if folder_kind=='sent': return 'applied',72
    return 'reply',55


def _norm_subject(value):
    text=str(value or '').strip()
    while True:
        newer=re.sub(r'(?i)^\s*(?:re|fw|fwd)\s*:\s*','',text).strip()
        if newer==text: break
        text=newer
    return re.sub(r'\s+',' ',text).strip().lower()


def _find_application(msg,subject,text,kind):
    portal_id=msg.get('X-ToughDev-Portal-Application-ID')
    if portal_id and str(portal_id).isdigit():
        return Application.objects.filter(pk=int(portal_id),deleted_at__isnull=True).first()
    refs=[]
    for h in ('In-Reply-To','References'):
        refs.extend(re.findall(r'<[^>]+>',str(msg.get(h,'') or '')))
    if refs:
        app=Application.objects.filter(imap_message_id__in=refs,deleted_at__isnull=True).first()
        if app: return app
    fwd=forwarded_headers(text)
    subjects={x for x in (_norm_subject(subject),_norm_subject(fwd.get('subject'))) if x}
    from_addr=original_sender_from_body(text)[1]
    direct_addrs={a.lower() for _,a in getaddresses([msg.get('From',''),msg.get('To',''),msg.get('Cc','')]) if a}
    if from_addr: direct_addrs.add(from_addr)
    # First prefer exact/contained subject matches against existing application drafts.
    qs=Application.objects.select_related('opportunity').filter(deleted_at__isnull=True,opportunity__user_deleted=False).order_by('-updated_at')[:1000]
    for app in qs:
        candidates={_norm_subject(app.email_subject),_norm_subject(app.opportunity.title)}-{''}
        if subjects and candidates and any(a==b or (len(a)>12 and a in b) or (len(b)>12 and b in a) for a in subjects for b in candidates):
            return app
    # Forwarded notifications often have generic subjects. Use company/contact evidence as a
    # secondary match, but only when it resolves to one existing application.
    company_hints={contact_company_from_email(a).lower() for a in direct_addrs if contact_company_from_email(a)}
    if company_hints:
        matches=[a for a in qs if str(a.opportunity.company or '').strip().lower() in company_hints]
        if len(matches)==1: return matches[0]
    # Finally match strong role/company strings found in the embedded forwarded body.
    blob=re.sub(r'\s+',' ',str(text or '')).lower()
    matches=[]
    for app in qs:
        role=str(app.opportunity.title or '').strip().lower(); company=str(app.opportunity.company or '').strip().lower()
        if company and len(company)>=3 and company in blob and role and len(role)>=5:
            key=' '.join(role.split()[:4])
            if key in blob or role in blob: matches.append(app)
    return matches[0] if len(matches)==1 else None


def _propose_import(msg,text,subject,dt,kind):
    h=forwarded_headers(text); original_from=original_sender_from_body(text)[1]
    role=re.sub(r'(?i)^(re|fw|fwd):\s*','',h.get('subject') or subject or '')[:300]
    if not role: return False
    if ImportCandidate.objects.filter(raw_excerpt__icontains=role[:80],source='mail').exists(): return False
    ImportCandidate.objects.create(source='mail',role_title=role,email=original_from or '',date_applied=dt if kind=='sent' else None,channel='email',confidence=65 if original_from else 45,raw_excerpt=text[:1500])
    return True


def scan_folder(folder,kind,limit=300):
    profile=active_profile(); im=connect(profile)
    stats={'folder':folder,'read':0,'imported':0,'updated':0,'errors':[]}
    try:
        if not ensure_folder(im,folder):
            stats['errors'].append(f'Could not open folder {folder}')
            return stats
        typ,data=im.uid('search',None,'ALL')
        if typ!='OK':
            stats['errors'].append(f'Could not list messages in {folder}')
            return stats
        uids=(data[0].decode().split() if data and data[0] else [])[-limit:]
        for uid in uids:
            try:
                typ,raw=im.uid('fetch',uid,'(RFC822)')
                if typ!='OK' or not raw or not raw[0] or not isinstance(raw[0],tuple):
                    stats['errors'].append(f'{folder} UID {uid}: fetch failed'); continue
                msg=email.message_from_bytes(raw[0][1]); text=body_text(msg)
                sender=decode_value(msg.get('From','')); fwd_name,fwd_addr=original_sender_from_body(text); subject=decode_value(msg.get('Subject',''))
                try: dt=parsedate_to_datetime(msg.get('Date')) if msg.get('Date') else timezone.now()
                except Exception: dt=timezone.now()
                if dt and timezone.is_naive(dt): dt=dt.replace(tzinfo=timezone.get_current_timezone())
                app=_find_application(msg,subject,text,kind)
                state,confidence=_classify(text,subject,kind)
                html=body_html(msg)
                event=MailEvent.objects.filter(folder=folder,uid=uid).order_by('-occurred_at').first()
                defaults={'kind':kind,'application':app,'subject':subject,'sender':sender,'recipients':decode_value(msg.get('To','')),'message_id':msg.get('Message-ID',''),'body_excerpt':text[:1600],'body_text':text,'body_html':html,'delivery_status':('observed_sent' if kind=='sent' else ''),'server':f'IMAP {profile.imap_host}:{profile.imap_port}','raw_original_sender':f'{fwd_name} <{fwd_addr}>' if fwd_addr else '','classification':state,'confidence':confidence,'occurred_at':dt or timezone.now(),'metadata':{'forwarded_headers':forwarded_headers(text),'inferred_application_status':state,'template':profile.template}}
                if event:
                    for field,value in defaults.items(): setattr(event,field,value)
                    event.save(update_fields=list(defaults.keys()))
                else:
                    event=MailEvent.objects.create(folder=folder,uid=uid,**defaults)
                extract_human_contacts(msg,text,app.opportunity.company if app else '')
                stats['read']+=1
                if app:
                    previous=app.status
                    if state in dict(Application.STATUS):
                        app.status=state
                    if state=='applied' and not app.applied_at:
                        app.applied_at=dt or timezone.now(); app.date_added=timezone.now()
                    if state in ('applied','reply','interview','rejected','accepted','closed'):
                        app.opportunity.status='applied' if state=='applied' else ('closed' if state in ('rejected','accepted','closed') else app.opportunity.status)
                        app.opportunity.save(update_fields=['status','updated_at'])
                    app.save()
                    if app.status!=previous: stats['updated']+=1
                elif _propose_import(msg,text,subject,dt,kind):
                    stats['imported']+=1
            except Exception as exc:
                stats['errors'].append(f'{folder} UID {uid}: {str(exc)[:220]}')
        return stats
    finally:
        try: im.logout()
        except Exception: pass


def sync_mailbox():
    p=active_profile()
    if not p:
        return {'imported':0,'updated':0,'read':0,'folders':{},'errors':['No active email profile configured.']}
    result={'imported':0,'updated':0,'read':0,'folders':{},'errors':[]}
    for label,folder,kind in [('Inbox',p.inbox_folder,'inbox'),('Sent',p.sent_folder,'sent'),('Drafts',p.drafts_folder,'draft')]:
        try:
            st=scan_folder(folder,kind)
        except Exception as exc:
            st={'folder':folder,'read':0,'imported':0,'updated':0,'errors':[str(exc)]}
        result['folders'][label]={'name':folder,'read':st.get('read',0)}
        result['read']+=int(st.get('read') or 0); result['imported']+=int(st.get('imported') or 0); result['updated']+=int(st.get('updated') or 0)
        result['errors'].extend(st.get('errors') or [])
    # Backward-compatible counters for scripts that used the old payload.
    result['inbox']=result['folders'].get('Inbox',{}).get('read',0); result['sent']=result['folders'].get('Sent',{}).get('read',0); result['drafts']=result['folders'].get('Drafts',{}).get('read',0)
    ps=PortalSettings.objects.get_or_create(pk=1)[0]; ps.last_mail_sync=timezone.now(); ps.save(update_fields=['last_mail_sync','updated_at'])
    result['scanned_at']=timezone.now().isoformat()
    return result

def fetch_event_body(event):
    """Fetch the full plain-text body for a stored MailEvent when its IMAP UID is available."""
    if event.folder and event.uid:
        profile=active_profile()
        if profile:
            im=connect(profile)
            try:
                if ensure_folder(im,event.folder):
                    typ,raw=im.uid('fetch',str(event.uid),'(RFC822)')
                    if typ=='OK' and raw and raw[0] and isinstance(raw[0],tuple):
                        msg=email.message_from_bytes(raw[0][1])
                        return body_text(msg), True
            finally:
                try: im.logout()
                except Exception: pass
    return event.body_excerpt or '', False


def browse_folder(profile, folder, limit=50):
    """Return lightweight IMAP message rows without storing them in ScoutBox."""
    im=connect(profile)
    try:
        typ,_=im.select(f'"{folder}"', readonly=True)
        if typ!='OK': raise RuntimeError(f'Could not open IMAP folder: {folder}')
        typ,data=im.uid('search',None,'ALL')
        if typ!='OK': return []
        uids=(data[0].decode().split() if data and data[0] else [])[-max(1,min(int(limit or 50),100)):]
        rows=[]
        for uid in reversed(uids):
            typ,raw=im.uid('fetch',uid,'(BODY.PEEK[HEADER.FIELDS (DATE FROM TO CC SUBJECT MESSAGE-ID)])')
            if typ!='OK' or not raw or not raw[0] or not isinstance(raw[0],tuple): continue
            msg=email.message_from_bytes(raw[0][1])
            try:
                dt=parsedate_to_datetime(msg.get('Date')) if msg.get('Date') else None
                if dt and timezone.is_naive(dt): dt=dt.replace(tzinfo=timezone.get_current_timezone())
                when=timezone.localtime(dt).strftime('%d/%m/%Y %H:%M:%S') if dt else ''
            except Exception: when=decode_value(msg.get('Date',''))
            rows.append({'uid':str(uid),'subject':decode_value(msg.get('Subject','')),'sender':decode_value(msg.get('From','')),'recipients':decode_value(msg.get('To','')),'cc':decode_value(msg.get('Cc','')),'date':when,'message_id':msg.get('Message-ID','')})
        return rows
    finally:
        try: im.logout()
        except Exception: pass


def fetch_imap_message(profile, folder, uid):
    """Return a full message for the interactive IMAP browser."""
    im=connect(profile)
    try:
        typ,_=im.select(f'"{folder}"', readonly=True)
        if typ!='OK': raise RuntimeError(f'Could not open IMAP folder: {folder}')
        typ,raw=im.uid('fetch',str(uid),'(BODY.PEEK[])')
        if typ!='OK' or not raw or not raw[0] or not isinstance(raw[0],tuple): raise RuntimeError('Message could not be retrieved.')
        msg=email.message_from_bytes(raw[0][1])
        try:
            dt=parsedate_to_datetime(msg.get('Date')) if msg.get('Date') else None
            if dt and timezone.is_naive(dt): dt=dt.replace(tzinfo=timezone.get_current_timezone())
            when=timezone.localtime(dt).strftime('%d/%m/%Y %H:%M:%S') if dt else ''
        except Exception: when=decode_value(msg.get('Date',''))
        return {'uid':str(uid),'folder':folder,'subject':decode_value(msg.get('Subject','')),'sender':decode_value(msg.get('From','')),'recipients':decode_value(msg.get('To','')),'cc':decode_value(msg.get('Cc','')),'date':when,'message_id':msg.get('Message-ID',''),'body_text':body_text(msg),'body_html':body_html(msg)}
    finally:
        try: im.logout()
        except Exception: pass


def delete_imap_draft(profile, folder, uid):
    if (folder or '').strip().lower() != (profile.drafts_folder or 'Drafts').strip().lower():
        raise RuntimeError('ScoutBox only permits deletion from the configured Drafts folder.')
    im=connect(profile)
    try:
        typ,_=im.select(f'"{folder}"')
        if typ!='OK': raise RuntimeError('Drafts folder could not be opened.')
        if not _delete_uid(im,uid): raise RuntimeError('Draft could not be deleted.')
        return True
    finally:
        try: im.logout()
        except Exception: pass


def populate_test_messages(profile):
    """Append timestamped IMAP Browser test messages to Inbox, Drafts and Sent.

    This deliberately works for both Internal Development and External Mail profiles. It
    only APPENDs messages through the configured IMAP account; no message is delivered
    through SMTP/Resend and no external recipient is contacted.
    """
    im = connect(profile)
    now = timezone.localtime(timezone.now())
    stamp = now.strftime('%Y-%m-%d %H:%M:%S %Z')
    subject_stamp = now.strftime('%Y-%m-%d %H:%M:%S')
    address = profile.imap_email or profile.imap_username or 'candidate@application.test'
    samples = [
        (profile.inbox_folder or 'INBOX', None, f'ScoutBox IMAP test · Inbox · {subject_stamp}', 'recruiter@scoutbox.test', address,
         f'Hello,\n\nThis is a ScoutBox IMAP Browser Inbox test message.\nCreated: {stamp}\nMailbox profile: {profile.get_template_display()}\n\nIt represents an inbound recruiter reply.\n'),
        (profile.drafts_folder or 'Drafts', '(\\Draft)', f'ScoutBox IMAP test · Draft · {subject_stamp}', address, 'hiring@scoutbox.test',
         f'Hello,\n\nThis is a ScoutBox IMAP Browser Draft test message.\nCreated: {stamp}\nMailbox profile: {profile.get_template_display()}\n\nIt represents an unsent application draft.\n'),
        (profile.sent_folder or 'Sent', '(\\Seen)', f'ScoutBox IMAP test · Sent · {subject_stamp}', address, 'hiring@scoutbox.test',
         f'Hello,\n\nThis is a ScoutBox IMAP Browser Sent test message.\nCreated: {stamp}\nMailbox profile: {profile.get_template_display()}\n\nIt represents a sent application.\n'),
    ]
    count = 0
    try:
        for folder, flags, subject, sender, recipient, body in samples:
            ensure_folder(im, folder)
            msg = EmailMessage()
            msg['From'] = sender
            msg['To'] = recipient
            msg['Subject'] = subject
            msg['Date'] = format_datetime(timezone.now())
            msg['Message-ID'] = f'<scoutbox-imap-test-{uuid.uuid4().hex}@scoutbox.test>'
            msg.set_content(body)
            typ, _ = im.append(folder, flags, imaplib.Time2Internaldate(timezone.now().timestamp()), msg.as_bytes())
            if typ != 'OK':
                raise RuntimeError(f'Could not append test message to {folder}.')
            normalized_folder=(folder or '').strip().lower()
            kind='inbox'
            if normalized_folder==(profile.drafts_folder or 'Drafts').strip().lower(): kind='draft'
            elif normalized_folder==(profile.sent_folder or 'Sent').strip().lower(): kind='sent'
            MailEvent.objects.create(
                kind=kind, subject=subject, sender=sender, recipients=recipient,
                message_id=str(msg['Message-ID'] or ''), folder=folder,
                body_excerpt=body[:800], body_text=body, delivery_status='test',
                server=f'IMAP {profile.imap_host}:{profile.imap_port}',
                occurred_at=timezone.now(), metadata={'test_message':True,'mailbox_template':profile.template,'created_at':stamp},
            )
            count += 1
        return count
    finally:
        try: im.logout()
        except Exception: pass
