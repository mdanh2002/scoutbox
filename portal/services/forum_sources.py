"""Forum discovery source catalog and native forum acquisition helpers.

Forum support is deliberately implemented as ordinary SearchSource presets with
``source_type='forum'`` and ``direct_adapter='forum_generic'``.  Native forum search
paths (Discourse JSON/RSS, phpBB-style search URLs, Stack Exchange APIs/search pages,
feeds and deterministic search pages) are attempted before ScoutBox falls back to the
normal indexed search path used for enabled source domains.

Reddit and existing 0.10.58 community/direct sources are intentionally not seeded here;
they already have owners in the existing codebase.
"""
from __future__ import annotations

import re
import urllib.parse
from typing import Iterable

from bs4 import BeautifulSoup

FORUM_CATEGORY = 'Forums'
FORUM_SOURCE_TYPE = 'forum'
FORUM_DIRECT_ADAPTER = 'forum_generic'

# Names/domains owned by 0.10.58 adapters or explicit user request exclusions.  The seed
# step skips these to avoid duplicate source ownership during upgrades.
EXISTING_01058_COMMUNITY_NAMES = {
    'Reddit', 'GitHub', 'GitLab', 'Hacker News', 'Lobsters', 'DEV Community',
    'Indie Hackers', 'Facebook public posts', 'Company career pages',
}
EXISTING_01058_COMMUNITY_DOMAINS = {
    'reddit.com', 'github.com', 'gitlab.com', 'news.ycombinator.com', 'lobste.rs',
    'dev.to', 'indiehackers.com', 'facebook.com',
}

# Compact intent phrases used with campaign/Profile terms. These are rotated by callers;
# this is intentionally not a single huge Boolean query.
FORUM_INTENT_PHRASES = [
    'looking for contractor', 'contractor wanted', 'consultant wanted', 'looking to hire',
    'hiring engineer', 'developer needed', 'need someone', 'looking for someone',
    'paid help', 'paid project', 'freelance', 'contract work', 'implementation help',
    'debugging help', 'firmware help', 'PCB help', 'FPGA help', 'driver help',
    'reverse engineering help', 'maintainer wanted', 'bounty available',
    'technical writer', 'documentation help',
]

FORUM_OPPORTUNITY_RE = re.compile(
    r'(?i)\b(?:hiring|looking\s+(?:to\s+hire|for\s+(?:someone|a\s+(?:developer|engineer|contractor|consultant|freelancer|specialist)))|'
    r'(?:developer|engineer|programmer|contractor|consultant|freelancer|specialist|technical\s+writer|maintainer)\s+(?:needed|wanted)|'
    r'paid\s+(?:help|project|work|support|issue|bounty)|contract\s+(?:work|project)|consulting|consultancy|freelance|'
    r'need\s+(?:someone|help|an?\s+(?:expert|developer|engineer|contractor|consultant))|'
    r'implementation\s+help|debugging\s+help|firmware\s+help|pcb\s+help|fpga\s+help|driver\s+help|'
    r'reverse\s+engineering\s+help|maintainer\s+wanted|bounty\s+available|documentation\s+help)\b'
)

FORUM_NOISE_RE = re.compile(
    r'(?i)\b(?:homework|assignment|exam|school\s+project|tutorial|how\s+do\s+i\s+learn|'
    r'free\s+help|volunteer\s+only|no\s+budget|solved|resolved|closed|spam)\b'
)

FORUM_TECH_FALLBACK_TERMS = [
    'embedded', 'firmware', 'STM32', 'ESP32', 'microcontroller', 'RTOS', 'embedded Linux',
    'Yocto', 'Buildroot', 'OpenWrt', 'FPGA', 'PCB', 'KiCad', 'Qt', 'C++', 'Linux driver',
    'reverse engineering', 'emulator', 'DOSBox', 'legacy system', '6502', 'technical writing',
]

# One flat catalog for Configuration > Search Sources > Forums.  Each entry uses its native
# capability first where known, then may participate in site: fallback search.
FORUM_SOURCE_PRESETS = [
    {'name':'6502.org Forums', 'base_url':'http://forum.6502.org', 'software':'phpbb', 'search_path':'/search.php', 'priority':66, 'terms':['6502','assembly','retro computing','homebrew computer']},
    {'name':'All About Circuits Forum', 'base_url':'https://forum.allaboutcircuits.com', 'software':'xenforo', 'search_path':'/search/search', 'priority':78, 'terms':['electronics','embedded','circuit','PCB','firmware']},
    {'name':'AmigaWorld Forums', 'base_url':'https://amigaworld.net', 'software':'custom', 'search_path':'/modules/newbb/search.php', 'priority':62, 'terms':['Amiga','retro computing','legacy software','driver']},
    {'name':'Arduino Forum', 'base_url':'https://forum.arduino.cc', 'software':'discourse', 'search_path':'/search.json', 'priority':92, 'terms':['Arduino','ESP32','embedded','sensor','firmware','Jobs and Paid Consultancy']},
    {'name':'Arch Linux Forums', 'base_url':'https://bbs.archlinux.org', 'software':'fluxbb', 'search_path':'/search.php', 'priority':48, 'terms':['Linux','driver','build system','toolchain']},
    {'name':'AtariAge Forums', 'base_url':'https://forums.atariage.com', 'software':'ips', 'search_path':'/search/', 'priority':62, 'terms':['Atari','retro computing','cartridge','6502','hardware']},
    {'name':'Bambu Lab Community Forum', 'base_url':'https://forum.bambulab.com', 'software':'discourse', 'search_path':'/search.json', 'priority':44, 'terms':['3D printer','firmware','hardware','embedded']},
    {'name':'CodeGuru Forums', 'base_url':'https://forums.codeguru.com', 'software':'vbulletin', 'search_path':'/search.php', 'priority':45, 'terms':['C++','software developer','Windows','systems']},
    {'name':'Crowd Supply Project Communities', 'base_url':'https://www.crowdsupply.com', 'software':'site', 'search_path':'/search', 'priority':55, 'terms':['hardware startup','open hardware','firmware','PCB']},
    {'name':'DaniWeb Community', 'base_url':'https://www.daniweb.com', 'software':'site', 'search_path':'/search', 'priority':42, 'terms':['software developer','C++','Python','help wanted']},
    {'name':'Debian User Forums', 'base_url':'https://forums.debian.net', 'software':'phpbb', 'search_path':'/search.php', 'priority':44, 'terms':['Linux','driver','package','embedded Linux']},
    {'name':'diyAudio Forum', 'base_url':'https://www.diyaudio.com/community', 'software':'xenforo', 'search_path':'/search/search', 'priority':68, 'terms':['audio','PCB','analog','firmware','electronics']},
    {'name':'DOSBox Community', 'base_url':'https://www.vogons.org', 'software':'phpbb', 'search_path':'/search.php', 'priority':65, 'skip_seed':True, 'terms':['DOSBox','emulation','compatibility','legacy software']},
    {'name':'EDAboard / Forum for Electronics', 'base_url':'https://www.edaboard.com', 'software':'xenforo', 'search_path':'/search/search', 'priority':72, 'terms':['FPGA','EDA','electronics','PCB','embedded']},
    {'name':'EEVblog Forum', 'base_url':'https://www.eevblog.com/forum', 'software':'smf', 'search_path':'/search/', 'priority':95, 'terms':['electronics','embedded','FPGA','PCB','test equipment','firmware']},
    {'name':'Electro-Tech-Online Forum', 'base_url':'https://www.electro-tech-online.com', 'software':'xenforo', 'search_path':'/search/search', 'priority':86, 'terms':['electronics','embedded','PIC','PCB','Jobs and Careers']},
    {'name':'element14 Community', 'base_url':'https://community.element14.com', 'software':'site', 'search_path':'/search', 'priority':80, 'terms':['Raspberry Pi','electronics','PCB','embedded','maker']},
    {'name':'English Amiga Board', 'base_url':'https://eab.abime.net', 'software':'vbulletin', 'search_path':'/search.php', 'priority':62, 'terms':['Amiga','retro computing','driver','reverse engineering']},
    {'name':'Espressif Community', 'base_url':'https://esp32.com', 'software':'phpbb', 'search_path':'/search.php', 'priority':76, 'terms':['ESP32','ESP-IDF','firmware','IoT','BLE']},
    {'name':'Fedevel Forum', 'base_url':'https://forum.fedevel.com', 'software':'discourse', 'search_path':'/search.json', 'priority':74, 'terms':['PCB','hardware design','FPGA','board bring-up','Altium']},
    {'name':'Framework Community', 'base_url':'https://community.frame.work', 'software':'discourse', 'search_path':'/search.json', 'priority':48, 'terms':['hardware','firmware','Linux','driver']},
    {'name':'FreeRTOS Community Forums', 'base_url':'https://forums.freertos.org', 'software':'discourse', 'search_path':'/search.json', 'priority':70, 'terms':['FreeRTOS','RTOS','embedded','firmware']},
    {'name':'Gentoo Forums', 'base_url':'https://forums.gentoo.org', 'software':'phpbb', 'search_path':'/search.php', 'priority':42, 'terms':['Linux','toolchain','driver','systems']},
    {'name':'Hackaday.io Projects', 'base_url':'https://hackaday.io', 'software':'site', 'search_path':'/search', 'priority':58, 'terms':['hardware project','firmware','PCB','reverse engineering']},
    {'name':'Hackaday Community', 'base_url':'https://hackaday.com', 'software':'site', 'search_path':'/', 'priority':52, 'terms':['hardware','embedded','reverse engineering','maker']},
    {'name':'Hashnode Discussions', 'base_url':'https://hashnode.com', 'software':'site', 'search_path':'/search', 'priority':40, 'terms':['software developer','technical writing','developer documentation']},
    {'name':'KiCad Forum', 'base_url':'https://forum.kicad.info', 'software':'discourse', 'search_path':'/search.json', 'priority':90, 'terms':['KiCad','PCB layout','schematic','freelance PCB']},
    {'name':'LinuxQuestions.org', 'base_url':'https://www.linuxquestions.org/questions', 'software':'vbulletin', 'search_path':'/search.php', 'priority':52, 'terms':['Linux','driver','embedded Linux','sysadmin']},
    {'name':'LowEndTalk', 'base_url':'https://lowendtalk.com', 'software':'vanilla', 'search_path':'/search', 'priority':38, 'terms':['Linux','networking','sysadmin','server']},
    {'name':'Mbed OS Community Archive', 'base_url':'https://forums.mbed.com', 'software':'discourse', 'search_path':'/search.json', 'priority':50, 'terms':['Mbed','embedded','firmware','migration']},
    {'name':'Microchip Community', 'base_url':'https://forum.microchip.com', 'software':'site', 'search_path':'/s/global-search', 'priority':66, 'terms':['PIC','AVR','dsPIC','embedded C','firmware']},
    {'name':'Mikrocontroller.net Forum', 'base_url':'https://www.mikrocontroller.net', 'software':'site', 'search_path':'/search', 'priority':72, 'terms':['microcontroller','embedded','PCB','firmware','German']},
    {'name':'Nordic DevZone', 'base_url':'https://devzone.nordicsemi.com', 'software':'site', 'search_path':'/search', 'priority':64, 'terms':['nRF52','BLE','Matter','embedded','firmware']},
    {'name':'NXP Community', 'base_url':'https://community.nxp.com', 'software':'site', 'search_path':'/t5/forums/searchpage/tab/message', 'priority':62, 'terms':['i.MX','embedded Linux','BSP','secure boot','firmware']},
    {'name':'OpenWrt Forum', 'base_url':'https://forum.openwrt.org', 'software':'discourse', 'search_path':'/search.json', 'priority':68, 'terms':['OpenWrt','router firmware','embedded Linux','networking']},
    {'name':'OSDev Forum', 'base_url':'https://forum.osdev.org', 'software':'phpbb', 'search_path':'/search.php', 'priority':65, 'terms':['kernel','bootloader','OSDev','assembly','low-level']},
    {'name':'Pine64 Forum', 'base_url':'https://forum.pine64.org', 'software':'mybb', 'search_path':'/search.php', 'priority':45, 'terms':['ARM','Linux','firmware','driver','open hardware']},
    {'name':'Prusa Community Forum', 'base_url':'https://forum.prusa3d.com', 'software':'wpforo', 'search_path':'/search', 'priority':42, 'terms':['3D printer','firmware','hardware','embedded']},
    {'name':'PTT CodeJob', 'base_url':'https://www.ptt.cc/bbs/CodeJob', 'software':'site', 'search_path':'/search', 'priority':54, 'terms':['contract coding','part-time','ESP32','Taiwan']},
    {'name':'Qt Forum', 'base_url':'https://forum.qt.io', 'software':'nodebb', 'search_path':'/api/search', 'priority':80, 'terms':['Qt','embedded C++','HMI','contractor']},
    {'name':'Raspberry Pi Forums', 'base_url':'https://forums.raspberrypi.com', 'software':'phpbb', 'search_path':'/search.php', 'priority':88, 'terms':['Raspberry Pi','embedded Linux','Python','sensor','Wanted']},
    {'name':'Retro Computing Forum', 'base_url':'https://retrocomputingforum.com', 'software':'discourse', 'search_path':'/search.json', 'priority':64, 'terms':['retro computing','legacy software','hardware restoration','emulation']},
    {'name':'Reverse Engineering Stack Exchange', 'base_url':'https://reverseengineering.stackexchange.com', 'software':'stackexchange', 'search_path':'/search', 'priority':56, 'terms':['reverse engineering','binary analysis','firmware analysis','protocol']},
    {'name':'RISC-V International Forums', 'base_url':'https://forums.riscv.org', 'software':'discourse', 'search_path':'/search.json', 'priority':48, 'terms':['RISC-V','embedded','FPGA','toolchain']},
    {'name':'ScummVM Forums', 'base_url':'https://forums.scummvm.org', 'software':'phpbb', 'search_path':'/search.php', 'priority':58, 'terms':['ScummVM','emulation','reverse engineering','legacy games']},
    {'name':'ST Community', 'base_url':'https://community.st.com', 'software':'site', 'search_path':'/t5/forums/searchpage/tab/message', 'priority':66, 'terms':['STM32','motor control','Cube','embedded','firmware']},
    {'name':'Stack Overflow Collectives/Public Search', 'base_url':'https://stackoverflow.com', 'software':'stackexchange', 'search_path':'/search', 'priority':38, 'terms':['paid help','contractor','developer','embedded']},
    {'name':'The Things Network Forum', 'base_url':'https://www.thethingsnetwork.org/forum', 'software':'discourse', 'search_path':'/search.json', 'priority':68, 'terms':['LoRaWAN','IoT','gateway','sensor','embedded']},
    {'name':'TI E2E Community', 'base_url':'https://e2e.ti.com', 'software':'site', 'search_path':'/search', 'priority':62, 'terms':['DSP','power','analog','embedded','RF']},
    {'name':'Tindie Project Communities', 'base_url':'https://www.tindie.com', 'software':'site', 'search_path':'/search', 'priority':45, 'terms':['maker product','open hardware','firmware','PCB']},
    {'name':'Unity Forums', 'base_url':'https://discussions.unity.com', 'software':'discourse', 'search_path':'/search.json', 'priority':36, 'terms':['simulation','tooling','technical writing','HMI']},
    {'name':'Unreal Engine Forums', 'base_url':'https://forums.unrealengine.com', 'software':'discourse', 'search_path':'/search.json', 'priority':36, 'terms':['simulation','tooling','HMI','technical writing']},
    {'name':'Vintage Computer Federation Forums', 'base_url':'https://forum.vcfed.org', 'software':'xenforo', 'search_path':'/index.php?search/search', 'priority':64, 'terms':['vintage computer','retro computing','firmware','hardware repair']},
    {'name':'VOGONS', 'base_url':'https://www.vogons.org', 'software':'phpbb', 'search_path':'/search.php', 'priority':66, 'terms':['DOS','retro computing','emulation','compatibility','reverse engineering']},
    {'name':'Voron Design Forum', 'base_url':'https://forum.vorondesign.com', 'software':'xenforo', 'search_path':'/search/search', 'priority':40, 'terms':['3D printer','firmware','hardware','embedded']},
    {'name':'WebHostingTalk', 'base_url':'https://www.webhostingtalk.com', 'software':'vbulletin', 'search_path':'/search.php', 'priority':38, 'terms':['Linux','networking','server','sysadmin']},
    {'name':'Yocto Project Mailing Lists', 'base_url':'https://lists.yoctoproject.org', 'software':'groupsio', 'search_path':'/g/yocto/search', 'priority':60, 'terms':['Yocto','embedded Linux','BSP','build system']},
    {'name':'Buildroot Mailing Lists', 'base_url':'https://lists.buildroot.org', 'software':'mailman', 'search_path':'/pipermail/buildroot/', 'priority':58, 'terms':['Buildroot','embedded Linux','toolchain','BSP']},
    {'name':'Zephyr Project Discussions', 'base_url':'https://github.com/zephyrproject-rtos/zephyr/discussions', 'software':'existing_external', 'search_path':'', 'priority':0, 'skip_seed':True, 'terms':['Zephyr','RTOS','embedded']},
]


def _host(url: str) -> str:
    try:
        return (urllib.parse.urlsplit(url).hostname or '').casefold().removeprefix('www.')
    except Exception:
        return ''


def forum_catalog_entries(existing_names: Iterable[str] | None = None, existing_domains: Iterable[str] | None = None) -> list[dict]:
    """Return the seedable forum entries after conflict checks.

    Existing codebase/community sources are skipped by name and by base domain.  Entries
    marked ``skip_seed`` document intentional non-implementation (for example GitHub-owned
    discussions) and are not returned.
    """
    names={str(x or '').casefold() for x in (existing_names or [])}
    domains={str(x or '').casefold().removeprefix('www.') for x in (existing_domains or [])}
    blocked_names={x.casefold() for x in EXISTING_01058_COMMUNITY_NAMES}
    blocked_domains={x.casefold() for x in EXISTING_01058_COMMUNITY_DOMAINS}
    out=[]
    for entry in FORUM_SOURCE_PRESETS:
        if entry.get('skip_seed'):
            continue
        name=str(entry.get('name') or '').strip()
        base=str(entry.get('base_url') or '').strip()
        host=_host(base)
        if not name or not base:
            continue
        if name.casefold() in names or name.casefold() in blocked_names:
            continue
        if host and (host in blocked_domains or host in domains):
            continue
        clean={k:v for k,v in entry.items() if k not in {'skip_seed'}}
        out.append(clean)
        names.add(name.casefold())
        if host:
            domains.add(host)
    out.sort(key=lambda x: x['name'].casefold())
    return out


def build_forum_query_terms(campaign=None, search_profile=None, source_config=None, max_terms=12) -> list[str]:
    terms=[]
    def add(value):
        value=' '.join(str(value or '').replace('\xa0',' ').split()).strip(' ,;')
        if not value or len(value)>80:
            return
        low=value.casefold()
        if low not in {x.casefold() for x in terms}:
            terms.append(value)
    steering=(search_profile or {}).get('campaign_steering') or {}
    for raw in (steering.get('technologies') or []) + (steering.get('roles') or []):
        add(raw)
    for attr in ('technologies','role_families','extra_text'):
        raw=getattr(campaign,attr,'') if campaign is not None else ''
        for piece in re.split(r'[,;|\n]+',str(raw or '')):
            add(piece)
    for row in (search_profile or {}).get('skills',[])[:16]:
        if isinstance(row,dict): add(row.get('term'))
    for raw in (source_config or {}).get('forum_terms') or []:
        add(raw)
    for raw in FORUM_TECH_FALLBACK_TERMS:
        add(raw)
    return terms[:max(1,int(max_terms or 12))]


def build_forum_queries(campaign=None, search_profile=None, source_config=None, max_queries=6) -> list[str]:
    """Build broad native-forum fallback searches.

    The primary forum path browses known marketplace/jobs/recent listing pages and lets
    the normal ScoutBox AI pass decide campaign fit.  Native keyword fallback therefore
    stays deliberately broad: opportunity intent plus source-wide terms, not exact campaign
    terms such as a single niche technology.  This avoids nearly-always-empty URLs like
    /search?keywords=looking+for+contractor+qemu on forums whose marketplace posts rarely
    use that exact phrasing.
    """
    cfg=source_config or {}
    source_terms=[]
    for raw in list(cfg.get('forum_terms') or []) + FORUM_TECH_FALLBACK_TERMS:
        clean=' '.join(str(raw or '').split()).strip()
        if clean and clean.casefold() not in {x.casefold() for x in source_terms}:
            source_terms.append(clean)
    intents=['hiring','jobs','paid help','paid project','contractor','consultant','freelance','wanted','help wanted','looking for someone','maintainer wanted','technical writer']
    queries=[]
    # Native forum search is a fallback after browsing marketplace/listing pages. Keep it
    # broad and separate: no Boolean bundles, no parenthesized Boolean logic, and no rare
    # campaign technology glued to a hiring phrase. The LLM relevance pass decides fit.
    for intent in intents:
        if intent.casefold() not in {x.casefold() for x in queries}:
            queries.append(intent)
        if len(queries)>=max_queries:
            return queries
    return queries or ['paid project']


def default_forum_listing_paths(source_name='', software='') -> list[str]:
    """Best-effort browse targets for forum marketplace/recent listings.

    Exact category IDs differ by installation and can change; these paths are intentionally
    conservative and are tried before keyword search.  Failures are source-local and do not
    prevent later fallback.
    """
    name=str(source_name or '').casefold(); sw=str(software or '').casefold()
    paths=[]
    if 'arduino' in name:
        paths += ['/c/community/jobs-and-paid-consultancy/19.json','/c/community/jobs-and-paid-consultancy/19']
    if 'raspberry pi' in name:
        paths += ['/viewforum.php?f=63','/viewforum.php?f=37','/forums']
    if 'all about circuits' in name:
        paths += ['/forums/jobs-and-career-advising.5/','/forums']
    if 'electro-tech' in name:
        paths += ['/forums/jobs-and-careers.33/','/forums']
    if 'kicad' in name:
        paths += ['/latest.json','/latest']
    if 'eevblog' in name:
        paths += ['/index.php?action=recent','/jobs/','/projects/']
    if 'qt forum' in name:
        paths += ['/api/recent','/recent']
    if 'element14' in name:
        paths += ['/community/raspberry-pi','/community/technologies']
    if 'fedevel' in name or sw=='discourse':
        paths += ['/latest.json','/latest']
    elif sw=='nodebb':
        paths += ['/api/recent','/recent']
    elif sw in {'xenforo','ips'}:
        paths += ['/whats-new/posts/','/forums/']
    elif sw in {'phpbb','mybb','vbulletin','smf','fluxbb'}:
        paths += ['/search.php?search_id=active_topics','/']
    elif sw in {'groupsio','mailman'}:
        paths += ['/']
    else:
        paths += ['/']
    out=[]
    for path in paths:
        if path and path not in out:
            out.append(path)
    return out[:5]


def forum_listing_urls(base_url: str, software: str, source_config=None, source_name='') -> list[tuple[str, dict, str]]:
    """Return forum listing/category URLs to browse before keyword search."""
    base=(base_url or '').rstrip('/')
    cfg=source_config or {}
    configured=list(cfg.get('forum_listing_paths') or [])
    paths=configured or default_forum_listing_paths(source_name or cfg.get('forum_name',''), software)
    rows=[]; seen=set()
    for raw in paths:
        raw=str(raw or '').strip()
        if not raw: continue
        if raw.startswith(('http://','https://')):
            url=raw
        elif raw.startswith('?'):
            url=base + raw
        elif raw.startswith('/'):
            url=base + raw
        else:
            url=base + '/' + raw
        if url in seen: continue
        seen.add(url)
        rows.append((url,{},raw))
    return rows


def forum_search_url(base_url: str, software: str, search_path: str, query: str) -> tuple[str, dict]:
    """Build a native forum search URL/params for known forum software."""
    base=(base_url or '').rstrip('/')
    sw=(software or '').casefold()
    path=search_path or ''
    q=query.strip()
    if sw=='discourse':
        return base + (path or '/search.json'), {'q': q}
    if sw=='nodebb':
        return base + (path or '/api/search'), {'term': q, 'in':'titlesposts'}
    if sw=='stackexchange':
        return base + (path or '/search'), {'q': q}
    if sw in {'phpbb','mybb','vbulletin','xenforo','smf','fluxbb','wpforo','vanilla','groupsio','mailman','custom','site','ips'}:
        url=base + (path or '/search')
        param='q'
        if sw in {'phpbb','mybb','vbulletin','smf','fluxbb'}:
            param='keywords'
        elif sw=='xenforo':
            param='keywords'
        elif sw=='groupsio':
            param='q'
        return url, {param: q}
    return base, {'q': q}


def parse_forum_search_results(data, html_text='', *, base_url='', software='', limit=20) -> list[dict]:
    rows=[]
    if isinstance(data,dict):
        # Discourse-like listing JSON (/latest.json, category.json) exposes topics without posts.
        topic_list=data.get('topic_list') if isinstance(data.get('topic_list'),dict) else {}
        listing_topics=[]
        if isinstance(topic_list.get('topics'),list):
            listing_topics.extend([x for x in topic_list.get('topics') if isinstance(x,dict)])
        if isinstance(data.get('topics'),list) and not data.get('posts'):
            listing_topics.extend([x for x in data.get('topics') if isinstance(x,dict)])
        for topic in listing_topics:
            title=topic.get('title') or topic.get('fancy_title') or ''
            slug=topic.get('slug') or ''
            ident=topic.get('id') or topic.get('topic_id')
            url=topic.get('url') or ''
            if not url and ident:
                url=f"/t/{slug}/{ident}" if slug else f"/t/{ident}"
            if url and url.startswith('/'):
                url=base_url.rstrip('/')+url
            snippet=topic.get('excerpt') or topic.get('blurb') or title
            published=topic.get('created_at') or topic.get('last_posted_at') or topic.get('bumped_at') or ''
            rows.append({'title':title,'url':url,'snippet':snippet,'published_at':published,'item_id':ident or url,'_forum_browse_area':True})
            if len(rows)>=limit: return rows
        # Discourse-like search JSON.
        topics={}
        for topic in data.get('topics') or []:
            if isinstance(topic,dict):
                topics[str(topic.get('id') or '')]=topic
        posts=data.get('posts') or data.get('results') or []
        if isinstance(posts,list):
            for item in posts:
                if not isinstance(item,dict):
                    continue
                topic=topics.get(str(item.get('topic_id') or item.get('topicId') or '')) or {}
                title=item.get('title') or topic.get('title') or item.get('name') or item.get('subject')
                slug=topic.get('slug') or item.get('slug') or ''
                post_number=item.get('post_number') or item.get('postNumber') or 1
                url=item.get('url') or item.get('href') or ''
                if not url and topic.get('id'):
                    url=f"/t/{slug}/{topic.get('id')}/{post_number}" if slug else f"/t/{topic.get('id')}/{post_number}"
                if url and url.startswith('/'):
                    url=base_url.rstrip('/')+url
                snippet=item.get('blurb') or item.get('excerpt') or item.get('raw') or item.get('content') or ''
                published=item.get('created_at') or item.get('createdAt') or item.get('updated_at') or topic.get('created_at') or ''
                rows.append({'title':title,'url':url,'snippet':snippet,'published_at':published,'item_id':item.get('id') or item.get('post_id') or url})
                if len(rows)>=limit: return rows
    if html_text:
        soup=BeautifulSoup(html_text,'html.parser')
        seen=set()
        selectors='a[href]'
        for a in soup.select(selectors):
            href=str(a.get('href') or '').strip()
            if not href or href.startswith(('#','mailto:','javascript:')):
                continue
            if href.startswith('/'):
                href=base_url.rstrip('/')+href
            elif href.startswith('//'):
                href='https:'+href
            if not href.startswith(('http://','https://')):
                continue
            if _host(base_url) and _host(href) and _host(base_url) not in _host(href) and _host(href) not in _host(base_url):
                continue
            text=' '.join(a.get_text(' ',strip=True).split())
            if len(text)<4 or len(text)>220:
                continue
            lower=(href+' '+text).casefold()
            if any(x in lower for x in ('login','logout','register','memberlist','profile.php','ucp.php','reply','quote','search.php?search_id')):
                continue
            if href in seen:
                continue
            seen.add(href)
            parent=a.find_parent(['li','article','tr','div'])
            ctx=' '.join(parent.get_text(' ',strip=True).split()) if parent else text
            published=''
            if parent:
                t=parent.find('time') or parent.find(attrs={'datetime': True})
                if t:
                    published=str(t.get('datetime') or t.get('title') or t.get_text(' ',strip=True) or '').strip()
            rows.append({'title':text,'url':href,'snippet':ctx[:3000],'published_at':published,'item_id':href,'_forum_browse_area':True})
            if len(rows)>=limit:
                break
    return rows


def forum_result_looks_promising(row: dict, campaign=None, search_profile=None) -> bool:
    blob=' '.join(str(row.get(k) or '') for k in ('title','snippet')).casefold()
    if FORUM_NOISE_RE.search(blob) and not FORUM_OPPORTUNITY_RE.search(blob):
        return False
    if FORUM_OPPORTUNITY_RE.search(blob):
        return True
    # Browsed marketplace/recent listings intentionally go to the normal AI pass with a
    # lighter textual gate; many titles say only what the project is, not every hiring word.
    browse_area=bool(row.get('_forum_browse_area'))
    terms=build_forum_query_terms(campaign,search_profile,{},max_terms=20)
    tech_hit=any(str(t).casefold() in blob for t in terms if len(str(t))>=3)
    weak=bool(re.search(r'(?i)\b(?:need|wanted|looking|help|project|contract|consult|paid|bounty|hire|freelance|job|career|opening|role)\b',blob))
    if browse_area and not FORUM_NOISE_RE.search(blob):
        return bool(tech_hit or weak or len(str(row.get('title') or '')) >= 12)
    return bool(tech_hit and weak)

def forum_source_defaults(entry: dict) -> dict:
    """Build SearchSource defaults for one forum catalog entry."""
    cfg={
        'direct_adapter': FORUM_DIRECT_ADAPTER,
        'direct_capability': 'Native forum search/API first',
        'discovery_capability': 'Forum native search · Local + Cloud direct · indexed fallback',
        'forum': True,
        'forum_base_url': entry.get('base_url',''),
        'forum_software': entry.get('software',''),
        'forum_search_path': entry.get('search_path',''),
        'forum_listing_paths': list(entry.get('listing_paths') or default_forum_listing_paths(entry.get('name',''), entry.get('software',''))),
        'forum_terms': list(entry.get('terms') or []),
        'native_first': True,
        'indexed_fallback': True,
    }
    return {
        'category': FORUM_CATEGORY,
        'source_type': FORUM_SOURCE_TYPE,
        'base_url': entry.get('base_url',''),
        'enabled': True,
        'preferred_initial': False,
        'priority': int(entry.get('priority') or 50),
        'provider_weight': 100,
        'low_value_marketplace': False,
        'requires_credentials': False,
        'adapter_status': 'direct',
        'public_fallback': True,
        'notes': 'Forum source: ScoutBox uses native forum search/feed/API paths first, then bounded indexed fallback when needed.',
        'config_json': cfg,
    }


def seed_forum_sources(SearchSourceModel) -> tuple[int,int]:
    """Seed all non-conflicting forum sources and keep shipped forum config current.

    Returns (created, updated). Existing source names/domains are skipped so upgrades from
    0.10.58 and customized installs do not get duplicate community source ownership.
    """
    existing=list(SearchSourceModel.objects.all().values('name','base_url','source_type'))
    existing_names=[x.get('name') for x in existing]
    existing_domains=[]
    for x in existing:
        # Existing forum rows are allowed to be updated by name; non-forum duplicates are skipped.
        if str(x.get('source_type') or '').casefold() != FORUM_SOURCE_TYPE:
            existing_domains.append(_host(x.get('base_url') or ''))
    created=updated=0
    for entry in forum_catalog_entries(existing_names=[n for n in existing_names if not SearchSourceModel.objects.filter(name=n, source_type=FORUM_SOURCE_TYPE).exists()], existing_domains=existing_domains):
        defaults=forum_source_defaults(entry)
        obj,was_created=SearchSourceModel.objects.get_or_create(name=entry['name'], defaults=defaults)
        if was_created:
            created+=1
            continue
        if getattr(obj,'source_type','') != FORUM_SOURCE_TYPE:
            continue
        cfg=dict(getattr(obj,'config_json',None) or {})
        new_cfg=dict(defaults['config_json'])
        cfg.update(new_cfg)
        changed=[]
        for field,value in [('category',FORUM_CATEGORY),('source_type',FORUM_SOURCE_TYPE),('base_url',entry.get('base_url','')),('adapter_status','direct'),('public_fallback',True),('requires_credentials',False),('priority',int(entry.get('priority') or 50))]:
            if getattr(obj,field)!=value:
                setattr(obj,field,value); changed.append(field)
        if cfg != getattr(obj,'config_json',{}):
            obj.config_json=cfg; changed.append('config_json')
        if changed:
            obj.save(update_fields=list(dict.fromkeys(changed)))
            updated+=1
    return created,updated
