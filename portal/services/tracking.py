import itertools
import re
from urllib.parse import urljoin, urlparse

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from bs4 import BeautifulSoup
from django.db import IntegrityError, transaction
from django.utils import timezone

from portal.models import PortalSettings, TrackingLink, TrackingLinkRule, TrackingSuffixReserve

UA='Mozilla/5.0 ScoutBox/0.8.10'
STOPWORDS={'the','and','for','with','from','this','that','your','you','how','why','what','using','use','into','about','blog','article','toughdev','www','http','https','com'}
RESERVE_BATCH_SIZE=240
MARKDOWN_LINK_TITLE_RE=re.compile(r'^\s*\[([^\]]+)\]\((https?://[^)]+)\)\s*$',re.I)
BARE_URL_TITLE_RE=re.compile(r'^https?://\S+$',re.I)


def _title_text(value):
    return ' '.join(str(value or '').split()).strip()


def _title_is_placeholder(value):
    """Return True for link-shaped values that are presentation markup, not page titles."""
    text=_title_text(value)
    return bool(text and (MARKDOWN_LINK_TITLE_RE.match(text) or BARE_URL_TITLE_RE.match(text)))


def clean_article_title(value):
    """Normalize a stored title for legacy display/export paths."""
    text=_title_text(value)
    if not text:
        return ''
    match=MARKDOWN_LINK_TITLE_RE.match(text)
    if match:
        text=_title_text(match.group(1))
    if BARE_URL_TITLE_RE.match(text):
        return ''
    return text[:300]


def _title_key(value):
    return re.sub(r'[^a-z0-9]+','',_title_text(value).casefold())


def article_title_needs_refresh(value, destination_url='', rule_name='', base_path=''):
    """True when a stored title is missing or looks like a legacy slug/rule label."""
    text=_title_text(value)
    if not text or _title_is_placeholder(text):
        return True
    key=_title_key(text)
    if not key:
        return True
    # Older tracking rules often stored a cosmetic rule/slug label (for example
    # "Pictts") instead of the document's actual HTML title.  Treat an exact match
    # to the rule name, base-path slug, or destination slug as stale so the background
    # repair fetches the live page title.
    comparisons=[]
    if rule_name:
        comparisons.append(_title_key(rule_name))
    for raw in (base_path,destination_url):
        try:
            path=urlparse(str(raw or '')).path if '://' in str(raw or '') else str(raw or '')
        except Exception:
            path=str(raw or '')
        slug=path.rstrip('/').split('/')[-1] if path else ''
        if slug:
            comparisons.append(_title_key(slug))
    return bool(key and any(candidate and key==candidate for candidate in comparisons))


def _page_title_from_soup(soup, page_url=''):
    """Extract an actual page title while ignoring Markdown/URL/slug placeholders."""
    raw_title=soup.title.get_text(' ',strip=True) if soup.title else ''
    meta=[]
    for attrs in ({'property':'og:title'},{'name':'twitter:title'},{'name':'title'}):
        node=soup.find('meta',attrs=attrs)
        if node and node.get('content'):
            meta.append(node.get('content'))
    h=soup.find('h1')
    heading=h.get_text(' ',strip=True) if h else ''
    candidates=(meta+[heading,raw_title]) if _title_is_placeholder(raw_title) else ([raw_title]+meta+[heading])
    try:
        page_slug=(urlparse(str(page_url or '')).path or '').rstrip('/').split('/')[-1]
    except Exception:
        page_slug=''
    slug_key=_title_key(page_slug)
    for candidate in candidates:
        # A page can repeat the same malformed Markdown string in <title>, OG, and
        # Twitter metadata. Do not unwrap that to its link label (for example
        # "Pictts") and mistake it for the document title. Likewise, a legacy
        # metadata field containing only the URL slug is not a document title; keep
        # looking so a meaningful H1 can win.
        if _title_is_placeholder(candidate):
            continue
        cleaned=clean_article_title(candidate)
        if cleaned and slug_key and _title_key(cleaned)==slug_key:
            continue
        if cleaned:
            return cleaned
    return ''


def slug_word(s):
    return re.sub('[^a-z0-9]','',str(s or '').lower())[:28]


def suffix_word(s):
    """Return a compact article-native tracking extension.

    ToughDev's short-link matcher uses a startswith rule, so generated tracking URLs keep
    the article's native short stem intact and append only one/two article words.  The
    extension is letters-only and deliberately capped at 15 characters.
    """
    return re.sub('[^a-z]','',str(s or '').lower())[:15]


def _candidates(words):
    """Yield one- or two-word article extensions, never a title/slug dump."""
    clean=[]; seen=set()
    for raw in words:
        w=suffix_word(raw)
        if len(w)>=2 and w not in seen and w not in STOPWORDS:
            seen.add(w); clean.append(w); yield w
    for a,b in itertools.permutations(clean,2):
        x=(a+b)[:15]
        if len(x)>=2 and x not in seen:
            seen.add(x); yield x


def blog_base_url():
    return (PortalSettings.objects.get_or_create(pk=1)[0].tracking_blog_base_url or 'https://toughdev.com/blog').rstrip('/')


def _host_key(parsed):
    host=(parsed.hostname or '').lower().rstrip('.')
    return host[4:] if host.startswith('www.') else host


def _url_key(value):
    try:
        p=urlparse(value or '')
        if not p.scheme:
            return ''
        return f'{_host_key(p)}{(p.path or "/").rstrip("/") or "/"}'
    except Exception:
        return ''


def _stored_info(rule, original_url=''):
    slug=(rule.base_path or '').rstrip('/').split('/')[-1]
    words=[]
    for x in re.split('[,\n;| ]+',rule.article_keywords or ''):
        sx=slug_word(x)
        if sx and sx not in words:
            words.append(sx)
    try:
        article_path=urlparse(rule.destination_url).path or rule.base_path
        article_slug=article_path.rstrip('/').split('/')[-1]
    except Exception:
        article_path=rule.base_path; article_slug=slug
    return {
        'original_url': original_url or rule.destination_url,
        'resolved_url': rule.destination_url,
        'title': ('' if article_title_needs_refresh(rule.article_title,rule.destination_url,rule.name,rule.base_path) else clean_article_title(rule.article_title)) or article_slug.replace('-',' ').title(),
        'article_path': article_path,
        'article_slug': article_slug,
        'tracking_stem': slug_word(slug),
        'tracking_path': rule.base_path,
        'words': words,
        'status': 200,
        'cached': True,
    }


def _find_cached_rule(entered):
    value=(entered or '').strip()
    if not value:
        return None
    if re.match(r'^https?://',value,re.I):
        key=_url_key(value)
        if not key:
            return None
        for rule in TrackingLinkRule.objects.filter(enabled=True).only('id','name','base_path','destination_url','article_title','article_keywords','enabled'):
            if _url_key(rule.destination_url)==key:
                return rule
            base=urlparse(blog_base_url())
            root=f'{base.scheme}://{base.netloc}'
            if _url_key(urljoin(root,rule.base_path or '/'))==key:
                return rule
        return None
    short=value.strip('/').lower()
    for rule in TrackingLinkRule.objects.filter(enabled=True).only('id','name','base_path','destination_url','article_title','article_keywords','enabled'):
        path=(rule.base_path or '').strip('/').lower()
        if short==path or short==path.split('/')[-1]:
            return rule
    return None


def resolve_article(url, timeout=12):
    """Resolve an article URL and derive article-native suffix vocabulary."""
    entered=(url or '').strip()
    if not entered:
        raise ValueError('Enter an article path, short name, or URL.')
    base=blog_base_url()
    if re.match(r'^https?://',entered,re.I):
        original=entered
    else:
        original=base.rstrip('/')+'/'+entered.strip('/')
    try:
        r=requests.get(original,headers={'User-Agent':UA,'Accept-Language':'en-US,en;q=0.8'},timeout=timeout,allow_redirects=True,verify=False)
        r.raise_for_status()
    except Exception as exc:
        raise ValueError(f'Article could not be retrieved: {exc}')
    final=r.url; status=r.status_code
    ctype=(r.headers.get('content-type') or '').lower()
    if 'html' not in ctype and 'text/' not in ctype:
        raise ValueError(f'Article returned unsupported content type: {ctype or "unknown"}.')
    soup=BeautifulSoup(r.text,'html.parser')
    title=_page_title_from_soup(soup,final)
    for x in soup(['script','style','noscript']): x.extract()
    text=' '.join(soup.stripped_strings)[:12000]
    if not title:
        raise ValueError('Article exists but no page title could be detected.')

    bp=urlparse(base); fp=urlparse(final)
    if _host_key(fp) != _host_key(bp):
        raise ValueError(f'The resolved URL is not on the configured blog host ({bp.netloc}).')
    base_path=bp.path.rstrip('/') or '/'
    article_path=fp.path.rstrip('/') or '/'
    if article_path in ('','/') or article_path==base_path:
        raise ValueError('Invalid link, please try a different link.')
    slug=article_path.strip('/').split('/')[-1]
    # The native tracking stem comes from the URL the user/document supplied, before a
    # short article URL redirects to a long canonical /content/... slug.  Tracking links
    # live at the host root (for example /super8086xt) because ToughDev's redirect matcher
    # performs a startswith match on that native short stem.
    try:
        entered_path=(urlparse(original).path or '').rstrip('/')
    except Exception:
        entered_path=''
    entered_slug=(entered_path.split('/')[-1] if entered_path else '') or slug
    tracking_stem=slug_word(entered_slug) or slug_word(slug)
    if not tracking_stem:
        raise ValueError('Could not derive a safe article short path for tracking.')

    # Prefer short technical acronyms from the real page title (PC, XT, PIC, etc.), then
    # ordinary article words.  Extensions are letters-only and at most 15 characters.
    raw=[]
    raw += re.findall(r'\b[A-Z]{2,10}\b',title)
    raw += re.split(r'[-_./]+',slug)
    raw += re.findall(r'[A-Za-z][A-Za-z0-9]{1,}',title)
    raw += re.findall(r'[A-Za-z][A-Za-z0-9]{2,}',text[:5000])[:80]
    words=[]
    stem_letters=suffix_word(tracking_stem)
    for x in raw:
        sx=suffix_word(x)
        if len(sx)<2 or sx in STOPWORDS or sx==stem_letters: continue
        # Avoid redundant additions such as /super8086super.
        if sx and sx in stem_letters: continue
        if sx not in words: words.append(sx)
        if len(words)>=18: break
    if not words:
        words=['firmware','guide','notes','build','details']
    return {
        'original_url':original,'resolved_url':final,'title':title or slug.replace('-',' ').title(),
        'article_path':article_path,'article_slug':slug,'tracking_stem':tracking_stem,
        'tracking_path':'/'+tracking_stem,'words':words,'status':status,'cached':False,
    }


def _rule_words(rule):
    article_key=suffix_word((rule.base_path or '').rstrip('/').split('/')[-1])
    words=[]
    for x in re.split('[,\n;| ]+',rule.article_keywords or ''):
        sx=suffix_word(x)
        if len(sx)>=2 and sx!=article_key and sx not in article_key and sx not in words:
            words.append(sx)
    return words or ['notes','guide','build','setup','code','tools']


def _ai_suffix_candidates(rule, count):
    """Ask the configured routed model for a reserve batch in one GPU/model call."""
    count=max(20,min(int(count or 0),RESERVE_BATCH_SIZE))
    try:
        from portal.services.ai import generate
        prompt=(
            f'Generate {count} distinct short URL suffix tokens related to this technical article.\n'
            'Each token must be lowercase ASCII letters only, 2-15 characters, no spaces, punctuation, slashes, digits, or leading article slug. '
            'Prefer memorable technical words or compact two-word combinations. Output one token per line and nothing else.\n\n'
            f'Title: {rule.article_title or rule.name}\n'
            f'Keywords: {rule.article_keywords}\n'
        )
        raw=generate(prompt,stage='page_summarization',timeout=180)
    except Exception:
        return []
    values=[]
    for line in str(raw or '').splitlines():
        # Models sometimes number or bullet the requested lines; strip that framing only.
        line=re.sub(r'^\s*(?:[-*•]|\d+[.)])\s*','',line.strip().lower())
        value=suffix_word(line)
        if 2<=len(value)<=15 and value not in STOPWORDS and value not in values:
            values.append(value)
        if len(values)>=count:
            break
    return values


def _refill_reserve(rule, target=RESERVE_BATCH_SIZE):
    """Prepare a reusable reserve from one/two article-native words."""
    target=max(40,min(int(target or RESERVE_BATCH_SIZE),500))
    snapshot=TrackingSuffixReserve.objects.filter(rule=rule).first()
    snapshot_values=[suffix_word(x) for x in ((snapshot.suffixes if snapshot else []) or []) if 2<=len(suffix_word(x))<=15]
    if len(snapshot_values)>=target:
        return snapshot

    # Article-native extensions are deterministic words taken from the article itself.
    # Do not ask an AI model to invent a phrase or echo the full article title.
    ai_candidates=[]
    with transaction.atomic():
        reserve,_=TrackingSuffixReserve.objects.select_for_update().get_or_create(rule=rule)
        current=[suffix_word(x) for x in (reserve.suffixes or []) if 2<=len(suffix_word(x))<=15]
        if len(current)>=target:
            return reserve
        existing=set(current)
        used={suffix_word(x) for x in TrackingLink.objects.filter(rule=rule).values_list('suffix',flat=True) if suffix_word(x)}
        for suffix in ai_candidates:
            if suffix not in existing and suffix not in used:
                current.append(suffix); existing.add(suffix)
                if len(current)>=target:
                    break
        if len(current)<target:
            words=_rule_words(rule)
            generator=_candidates(words)
            cursor=max(0,int(reserve.cursor or 0)); skipped=0
            while skipped<cursor:
                try: next(generator); skipped+=1
                except StopIteration: break
            consumed=cursor
            while len(current)<target:
                try:
                    suffix=next(generator); consumed+=1
                except StopIteration:
                    break
                if suffix in existing or suffix in used:
                    continue
                current.append(suffix); existing.add(suffix)
            reserve.cursor=consumed
        reserve.suffixes=current
        reserve.generated_at=timezone.now()
        reserve.save(update_fields=['suffixes','cursor','generated_at','updated_at'])
        return reserve


def _pop_reserved_suffix(rule):
    with transaction.atomic():
        reserve=TrackingSuffixReserve.objects.select_for_update().filter(rule=rule).first()
        if not reserve or not reserve.suffixes:
            return ''
        values=list(reserve.suffixes)
        suffix=''
        while values and not suffix:
            candidate=suffix_word(values.pop(0))
            if 2<=len(candidate)<=15:
                suffix=candidate
        reserve.suffixes=values
        reserve.save(update_fields=['suffixes','updated_at'])
        return suffix


def reserve_count(rule):
    try:
        return len(rule.suffix_reserve.suffixes or [])
    except Exception:
        return 0


def ensure_rule_for_url(url, force_refresh=False):
    # Resolve the live document on every explicit test/generation. Cached rules are
    # still reused below, but their article title comes from the fetched HTML instead
    # of a slug-derived fallback left over from an older generation.
    info=resolve_article(url)
    rule=TrackingLinkRule.objects.filter(destination_url=info['resolved_url']).first() or _find_cached_rule(info['resolved_url'])
    if not rule:
        name=f"Auto · {info['article_slug']}"[:200]
        if TrackingLinkRule.objects.filter(name=name).exists():
            name=f"{name[:185]} · {TrackingLinkRule.objects.count()+1}"
        rule=TrackingLinkRule.objects.create(
            name=name,
            base_path=info['tracking_path'],
            destination_url=info['resolved_url'],
            article_title=info['title'],
            article_keywords=', '.join(info['words']),
            enabled=True,
        )
    else:
        changed=[]
        stored_title=clean_article_title(rule.article_title)
        if info['title'] and stored_title != info['title']: rule.article_title=info['title']; changed.append('article_title')
        elif stored_title != rule.article_title: rule.article_title=stored_title; changed.append('article_title')
        if not rule.article_keywords: rule.article_keywords=', '.join(info['words']); changed.append('article_keywords')
        if rule.base_path != info['tracking_path']: rule.base_path=info['tracking_path']; changed.append('base_path')
        if _url_key(rule.destination_url) != _url_key(info['resolved_url']): rule.destination_url=info['resolved_url']; changed.append('destination_url')
        if changed: rule.save(update_fields=changed)
    _refill_reserve(rule)
    return rule,info


def allocate(rule, application=None):
    """Allocate a locally unique tracking path without probing an uncreated URL.

    The destination article is validated by ``ensure_rule_for_url`` before allocation. A new
    tracking URL cannot be expected to return HTTP 200 until ScoutBox has persisted it and the
    external short-link endpoint can resolve it, so probing each candidate here incorrectly
    rejected every valid suffix on installations that return 404 for unknown paths. Database
    uniqueness is the source of truth, with IntegrityError handling the small race window.
    """
    base=rule.base_path.rstrip('/')
    # Tracking links are published beneath the configured Blog base URL, not at the
    # host root.  For example, a base URL of https://toughdev.com/blog plus the
    # short stem /fatfs and suffix integrating must produce
    # https://toughdev.com/blog/fatfsintegrating.
    public_base=blog_base_url().rstrip('/')
    attempts=0
    while attempts<720:
        suffix=_pop_reserved_suffix(rule)
        if not suffix:
            _refill_reserve(rule)
            suffix=_pop_reserved_suffix(rule)
            if not suffix:
                break
        attempts+=1
        stem_path=base+suffix
        full=public_base+'/'+stem_path.lstrip('/')
        path=urlparse(full).path or '/'
        if TrackingLink.objects.filter(path=path).exists() or TrackingLink.objects.filter(full_url=full).exists():
            continue
        try:
            with transaction.atomic():
                return TrackingLink.objects.create(
                    rule=rule,application=application,suffix=suffix,path=path,full_url=full
                )
        except IntegrityError:
            # A concurrent allocation may have claimed the same path after the pre-check.
            # Consume another reserved suffix instead of failing or performing a network probe.
            continue
    raise RuntimeError('Could not allocate a unique article-native suffix for this article.')


def allocate_for_url(url, application=None):
    rule,info=ensure_rule_for_url(url)
    link=allocate(rule,application)
    info=dict(info)
    info['reserve_remaining']=reserve_count(rule)
    return link,info


def preview_for_url(url):
    rule,info=ensure_rule_for_url(url)
    reserve=TrackingSuffixReserve.objects.filter(rule=rule).first()
    if not reserve or not reserve.suffixes:
        reserve=_refill_reserve(rule)
    sample=(reserve.suffixes or [''])[0] if reserve else ''
    return {'rule':rule,'info':info,'sample_suffix':sample,'reserve_count':reserve_count(rule)}
