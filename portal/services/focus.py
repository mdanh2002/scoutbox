"""Content-based Focus classification for ScoutBox list views.

Focus labels are deliberately *not* hard-coded.  Opportunities, Hidden Leads and
Address Book each maintain an independent taxonomy namespace.  Campaign names are
weak naming inspiration only: a campaign can help name a cluster when the record
content supports that topic, but it never assigns a Focus by itself.

Normal saves classify only the new/blank row.  Repair/recovery uses a same-list
batch clustering pass with balance checks so a taxonomy does not collapse into one
huge bucket or fragment into many one-item labels.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

FOCUS_UNCLASSIFIED = 'Unclassified'
FOCUS_TARGET_VERSION = '0.11.3'
_NAMESPACE_BY_MODEL = {
    'Opportunity': 'opportunities',
    'CompanyLead': 'hidden_leads',
    'Contact': 'address_book',
}
_STOP = {
    'a','an','and','or','the','to','of','for','in','on','with','from','at','as','by','is','are','be','this','that','their','our','your','you','we','it',
    'role','job','jobs','team','company','companies','senior','staff','lead','principal','junior','developer','specialist','remote','full','time','work','working','position','opportunity',
    'develop','developing','build','building','built','create','creating','deliver','delivering','provide','providing','key','responsibility','responsibilities','include','includes','including','required','requires','require','requirements','experience','experienced','knowledge','benefit','benefits','flexible','shift','shifts','remote-first','hybrid','onsite','on-site','office','offices','location','locations','salary','annual','hourly','usd','cad','eur','aud','gbp','dallas','houston','austin','boston','chicago','vancouver','toronto','london','spain','egypt','india','singapore','united','states','usa','us','uk','tx','ca','co','ct','fl','ny','pa','wa','bc','on','am',
    'ago','day','days','week','weeks','month','months','year','years','posted','posting','applicants','applicant','apply','applied','linkedin','user','users','agree','agreement','privacy','policy','terms','condition','conditions','click','clicking','continue','join','before','deciding','whether','would','useful','uses','used','good','fit','fits','more','exclusive','cover','letter','assistant','compensation','details','process','among','first','see','who','login','log','sign','signup','register','registration','share','save','view','original','easy','explore','legacy','general','broad','track','evaluation','integrating','integration','integrated','migration','migrate','migrating','grounded',
    'profile','candidate','hiring','careers','career','about','this','that','new','role','roles','opening','open','vacancy','vacancies','apply','needed','need','looking','seek','seeks','seeking',
}
# Words that are usually a role/seniority/form factor, not a useful focus by themselves.
_LABEL_GENERIC_TOKENS = {
    'engineer','engineering','developer','development','manager','management','specialist','consultant','analyst','architect','administrator','admin',
    'senior','staff','lead','principal','expert','role','job','jobs','software','systems','system','platform','platforms','technical','technology','application','applications',
    'service','services','solution','solutions','product','products','project','program','business','operations','operation','support','customer','customers','team','companies',
}

_MALFORMED_LABEL_RE = re.compile(
    r'(?i)^(?:develops?|developing|offers?|offering|provides?|providing|specializes?|specialising|focuses?|focusing|explores?|exploring|seeks?|seeking|uses?|using|builds?|building|works?|working)\b'
)
_MALFORMED_LABEL_PHRASES = (
    'develops offers','develops or offers','specializes embedded','specializes engineering',
    'focuses on','provides services','offers services','explore whether','would be useful',
)

_GENERIC_LABELS = {
    'software','software engineer','software engineering','engineering','technology','cloud technology','application engineer','applications engineer',
    'application engineering','developer','engineer','systems engineer','platform engineer','technical specialist','jobs','job','remote','general',
    'misc','miscellaneous','other','others','professional','business','technical','unknown','unclassified',
    'embedded','firmware','writing','would useful','explore firmware','legacy','c++','cplusplus','protocol reverse','security tls',
    'embedded integration','embedded low-level','cloud technology',
}


_USEFUL_EXACT_LABELS = {
    'machine learning','computer vision','technical support','it support','customer support','cloud devops','cloud infrastructure','cloud data migration',
    'data analytics','data engineering','business intelligence','gtm analytics','revenue operations','healthcare research','clinical data',
    'fintech engineering','payments','payments security','risk analytics','fraud detection','privacy compliance','security incident response',
    'blockchain security','network security','embedded firmware','firmware security','embedded linux','systems emulation','reverse engineering',
    'low-level systems','protocol connectivity','ai infrastructure','technical documentation','audio video systems','robotics systems','sales automation',
    'cybersecurity software','security software','dev tools','developer tools','hardware interfaces','iot firmware','iot applications','qa testing'
}

_CANONICAL_LABEL_REWRITES = {
    'buildroot yocto': 'Embedded Linux',
    'yocto buildroot': 'Embedded Linux',
    'qemu': 'Systems Emulation',
    'protocol reverse': 'Reverse Engineering',
    'protocol connectivity': 'Protocol & Connectivity',
    'connectivity protocol': 'Protocol & Connectivity',
    'security tls': 'Network Security',
    'tls security': 'Network Security',
    'writing': 'Technical Documentation',
    'technical writing': 'Technical Documentation',
    'documentation writing': 'Technical Documentation',
    'would useful': '',
    'explore firmware': 'Embedded Firmware',
    'legacy': '',
    'c++': '',
    'cplusplus': '',
    'embedded': '',
    'firmware': '',
    'embedded integration': 'Embedded Firmware',
    'hardware interfaces': 'Hardware Interfaces',
    'low level systems': 'Low-Level Systems',
    'customer technical support': 'Technical Support',
    'technical support': 'Technical Support',
    'it support': 'IT Support',
    'machine learning': 'Machine Learning',
    'learning engineer': 'Machine Learning',
    'cloud devops': 'Cloud DevOps',
    'devops cloud': 'Cloud DevOps',
    'gtm engineering analyst': 'GTM Analytics',
    'gtm analytics': 'GTM Analytics',
    'real world evidence': 'Healthcare Research',
    'healthcare research': 'Healthcare Research',
    'clinical data': 'Clinical Data',
    'unsecured installments': 'FinTech Engineering',
    'fintech engineering': 'FinTech Engineering',
    'payments engineering': 'Payments',
    'payment engineering': 'Payments',
    'embedded low-level': 'Low-Level Systems',
    'qa testing': 'QA & Testing',
    'quality assurance': 'QA & Testing',
    'retro computing': 'Vintage Systems',
    'retro systems': 'Vintage Systems',
    'vintage computing': 'Vintage Systems',
    'retro and legacy systems': 'Vintage Systems',
}


# Leads and Address Book have their own company/contact taxonomy namespace.  Labels
# that describe an open role's job function are not reused verbatim for company leads;
# otherwise an Opportunities group such as "Security Incident Response" can become a
# misleading Hidden Leads bucket for companies/contacts that merely mention those words.
_COMPANY_NAMESPACE_LABEL_REWRITES = {
    'security incident response': 'Cybersecurity Services',
    'network security': 'Cybersecurity Services',
    'blockchain security': 'Blockchain Security Companies',
    'firmware security': 'Firmware Security Companies',
    'qa & testing': 'Quality Engineering Services',
    'qa and testing': 'Quality Engineering Services',
    'technical support': 'Technical Services',
    'it support': 'IT Services',
    'cloud devops': 'Cloud Infrastructure Companies',
    'cloud infrastructure': 'Cloud Infrastructure Companies',
    'data engineering': 'Data Platform Companies',
    'data analytics': 'Analytics Companies',
    'machine learning': 'AI/ML Companies',
    'computer vision': 'Computer Vision Companies',
    'embedded firmware': 'Embedded Systems Companies',
    'embedded linux': 'Embedded Linux Companies',
    'low-level systems': 'Systems Software Companies',
    'protocol & connectivity': 'Connectivity Companies',
    'reverse engineering': 'Reverse Engineering Companies',
    'systems emulation': 'Emulation Companies',
    'fintech engineering': 'FinTech Companies',
    'payments': 'Payments Companies',
}
_OPPORTUNITY_ONLY_FOCUS_LABELS = set(_COMPANY_NAMESPACE_LABEL_REWRITES.keys())

_COMPANY_TOPIC_RULES = (
    ('Cybersecurity Services', (r'\bcyber\s*security\b', r'\bsecurity\s+(?:platform|services?|solutions?)\b', r'\bincident\s+response\b', r'\bsoc\b', r'\bsiem\b', r'\bthreat\s+(?:detection|hunting|intel)')),
    ('AI/ML Companies', (r'\bmachine\s+learning\b', r'\bai\s+(?:platform|product|solutions?|models?)\b', r'\bml\b', r'\bllm\b')),
    ('Data Platform Companies', (r'\bdata\s+(?:platform|intelligence|management|infrastructure|warehouse|lakehouse)\b', r'\banalytics\s+(?:platform|suite|product)\b', r'\bbusiness\s+intelligence\b')),
    ('Cloud Infrastructure Companies', (r'\bcloud\s+(?:infrastructure|platform|services?|hosting|computing)\b', r'\bcloud\s+and\s+ai\s+computing\b', r'\bkubernetes\b', r'\bdevops\b', r'\bsre\b')),
    ('Linux Systems Companies', (r'\blinux\s+(?:kernel|networking|systems?|platform|software)\b', r'\blinux\b.{0,80}\b(?:kernel|networking|low[-\s]+level|embedded|bsp|board\s+support)\b', r'\b(?:os|operating\s+systems?)\b.{0,80}\blow[-\s]+level\b', r'\bhigh[-\s]+performance\b.{0,80}\blinux\b')),
    ('Systems Software Companies', (r'\blow[-\s]+level\s+(?:systems?|software|engineering|stack)\b', r'\bbsp\b', r'\bboard\s+support\s+packages?\b', r'\bkernel\s+(?:engineering|development|software)\b')),
    ('Embedded Systems Companies', (r'\bembedded\s+(?:systems?|software|devices?)\b', r'\bfirmware\b', r'\brtos\b', r'\biot\b', r'\bdevice\s+drivers?\b')),
    ('Developer Tools Companies', (r'\bdeveloper\s+tools?\b', r'\bdevtools\b', r'\bsdk\b', r'\bapi\s+platform\b')),
    ('FinTech Companies', (r'\bfintech\b', r'\bpayments?\s+(?:platform|products?|company|solutions?)\b', r'\bbanking\s+(?:platform|services?)\b', r'\blending\b')),
    ('Healthcare Technology Companies', (r'\bhealthcare\s+(?:technology|platform|data)\b', r'\bclinical\s+(?:data|research|trials?)\b', r'\bmedical\s+(?:device|software|platform)\b')),
    ('Quality Engineering Services', (r'\bquality\s+engineering\b', r'\btest\s+automation\s+(?:platform|services?|solutions?)\b', r'\bqa\s+(?:platform|services?|automation)\b')),
)

_TOPIC_RULES = (
    ('QA & Testing', (r'\bmanual\s+qa\b', r'\bquality\s+assurance\b', r'\bqa\s+(?:engineer|testing|tester)\b', r'\btest\s+(?:cases?|plans?)\b', r'\bregression\s+testing\b', r'\bdefect\s+(?:reporting|reports?)\b')),
    ('Machine Learning', (r'\bmachine\s+learning\b', r'\bml\b', r'\bai\s+models?\b', r'\bmodel\s+(?:training|inference|evaluation)\b', r'\bscikit[-\s]?learn\b', r'\bpytorch\b', r'\btensorflow\b')),
    ('Technical Support', (r'\btechnical\s+support\b', r'\bhelpdesk\b', r'\bservice\s+desk\b', r'\bcustomer\s+support\b', r'\bticket(?:ing)?\b', r'\bit\s+certification')),
    ('GTM Analytics', (r'\bgtm\b', r'\bgo[-\s]?to[-\s]?market\b', r'\brevenue\s+(?:operations|analytics)\b', r'\bsales\s+analytics\b', r'\bgrowth\s+analytics\b')),
    ('Healthcare Research', (r'\breal[-\s]+world\s+evidence\b', r'\bclinical\s+(?:research|data|trials?)\b', r'\bhealthcare\s+(?:research|data|analytics)\b', r'\bmedical\s+research\b')),
    ('FinTech Engineering', (r'\bfintech\b', r'\bpayments?\b', r'\bunsecured\s+installments?\b', r'\blending\b', r'\bloan\b', r'\bbanking\b', r'\bcrypto(?:currency)?\s+exchange\b')),
    ('Data Analytics', (r'\bdata\s+analyst\b', r'\banalytics\b', r'\bbusiness\s+intelligence\b', r'\bbi\b', r'\bdashboard(?:ing)?\b', r'\bmetrics\b')),
    ('Cloud DevOps', (r'\bdevops\b', r'\bci/cd\b', r'\bdeployment\s+pipeline', r'\binfrastructure\s+as\s+code\b', r'\bterraform\b', r'\bkubernetes\b')),
    ('Blockchain Security', (r'\bblockchain\b', r'\bsmart\s+contract', r'\bchain\s+security', r'\bweb3\b', r'\bcrypto(?:currency)?\b')),
    ('Security Incident Response', (r'\bincident\s+response\b', r'\bsoc\b', r'\bsiem\b', r'\bthreat\s+(?:detection|hunting|intel)', r'\bmalware\b')),
    ('Network Security', (r'\boffensive\s+security\b', r'\bpenetration\s+test', r'\bvulnerab', r'\bzero\s+trust\b', r'\bxdr\b', r'\bedr\b', r'\btls\b', r'\bnetwork\s+security')),
    ('Systems Emulation', (r'\bemulation\b', r'\bemulator\b', r'\bqemu\b', r'\bvirtualization\b', r'\bvirtualisation\b', r'\bhypervisor\b')),
    ('Reverse Engineering', (r'\breverse\s+engineering\b', r'\bbinary\s+analysis\b', r'\bdebugger\b', r'\bdisassembl', r'\bdecompil')),
    ('Embedded Linux', (r'\bembedded\s+linux\b', r'\byocto\b', r'\bbuildroot\b', r'\bbsp\b', r'\bboard\s+support', r'\bdevice\s+driver', r'\blinux\s+kernel')),
    ('Embedded Firmware', (r'\bfirmware\b', r'\bmicrocontroller', r'\bembedded\b', r'\brtos\b', r'\bzephyr\b', r'\biot\b', r'\bbootloader\b')),
    ('Low-Level Systems', (r'\blow[-\s]+level\b', r'\bbare\s+metal\b', r'\bbios\b', r'\buefi\b', r'\bhardware\s+bring', r'\bjtag\b')),
    ('Protocol & Connectivity', (r'\bprotocol\b', r'\bmqtt\b', r'\btcp/?ip\b', r'\bble\b', r'\bbluetooth\b', r'\bwireless\b', r'\bconnectivity\b', r'\bcan\s+bus\b', r'\buart\b', r'\bi2c\b', r'\bspi\b')),
    ('Cloud Infrastructure', (r'\bcloud\s+infrastructure\b', r'\bplatform\s+engineering\b', r'\bsre\b', r'\bsite\s+reliability\b')),
    ('AI Infrastructure', (r'\bai\s+infrastructure\b', r'\bmlops\b', r'\bgpu\b', r'\bcuda\b', r'\bnvidia\b', r'\bmodel\s+serving\b')),
    ('Linux Systems', (r'\blinux\s+(?:kernel|networking|systems?|platform|software)\b', r'\blinux\b.{0,80}\b(?:kernel|networking|low[-\s]+level|embedded|bsp|board\s+support)\b', r'\b(?:os|operating\s+systems?)\b.{0,80}\blow[-\s]+level\b')),
    ('Computer Vision', (r'\bcomputer\s+vision\b', r'\bimage\s+processing\b', r'\bsegmentation\b', r'\bclassification\b', r'\bobject\s+detection\b')),
    ('Data Engineering', (r'\bdata\s+(?:engineering|migration|pipeline|streaming)\b', r'\betl\b', r'\bsnowflake\b', r'\bdatabricks\b')),
    ('Technical Documentation', (r'\btechnical\s+(?:writing|writer|documentation)\b', r'\bdeveloper\s+documentation\b', r'\bdocs\b')),
    ('Developer Tools', (r'\bdeveloper\s+tools\b', r'\bdebugging\s+tool', r'\btoolchain\b', r'\bsdk\b', r'\bapi\s+platform')),
    ('Audio & Video Systems', (r'\baudio\b', r'\bvideo\b', r'\bmultimedia\b', r'\bstreaming\b', r'\bcodec\b')),
    ('Robotics Systems', (r'\brobotics\b', r'\brobot\b', r'\bautonomous\b', r'\bslam\b', r'\bros2?\b')),
    ('Sales Automation', (r'\bsales\s+(?:automation|navigator|outreach|lead)\b', r'\bcrm\b', r'\bprospect(?:ing)?\b', r'\blinkedin\s+sales')),
    ('Fraud Detection', (r'\bfraud\b', r'\brisk\s+(?:detection|analytics|scoring)\b', r'\btransaction\s+monitoring')),
    ('Privacy & Compliance', (r'\bprivacy\b', r'\bcompliance\b', r'\bgdpr\b', r'\bdata\s+protection')),
    ('Cybersecurity Software', (r'\bcybersecurity\b', r'\bsecurity\s+(?:software|platform|tool)\b', r'\bendpoint\s+security')),
)


_CAMPAIGN_PREFIX_RE = re.compile(r'(?i)^\s*(?:profile|campaign|template|search|source)\s*[-—:]+\s*')


def _clean_text(value) -> str:
    """Extract topical text from JSON blobs without letting repair/provenance or
    scraped boilerplate dominate Focus labels.
    """
    safe_keys={
        'role_title','title','summary','highlight','description','skills','skill','technologies','technology','keywords','keyword','categories','category',
        'technical_areas','technical_area','job_categories','job_category','requirements','responsibilities','industry','industries','product','products',
        'service_line','business_area','domain','domains','ai_job_summary','local_pre_persistence_review',
    }
    noisy_fragments=('html','source_text','raw','page_text','scraped','reason','fit_reason','remote','location','country','provenance','focus','url','date','posted','fetch','error')

    def collect(obj, key_hint=''):
        key_l=str(key_hint or '').casefold()
        if any(x in key_l for x in noisy_fragments):
            return []
        if isinstance(obj,(str,int,float)):
            return [str(obj)] if (not key_l or key_l in safe_keys or any(k in key_l for k in safe_keys)) else []
        if isinstance(obj,list):
            parts=[]
            for item in obj[:24]:
                parts.extend(collect(item,key_hint))
            return parts
        if isinstance(obj,dict):
            parts=[]
            for k,v in obj.items():
                k_l=str(k or '').casefold()
                if k_l in safe_keys or any(sk in k_l for sk in safe_keys):
                    parts.extend(collect(v,k_l))
                elif isinstance(v,dict) and k_l in {'ai_job_summary','local_pre_persistence_review'}:
                    parts.extend(collect(v,k_l))
            return parts
        return []
    if value is None:
        return ''
    if isinstance(value,dict):
        return ' '.join(collect(value))
    return str(value)


def _record_text(record, include_campaign=True) -> str:
    cls=record.__class__.__name__
    namespace=_namespace_for_model(record)
    if cls=='Opportunity':
        # Focus is topical. Role-location and remote-work prose are intentionally
        # excluded so records do not drift into location/remote buckets.
        parts=[record.title,record.list_highlight,_clean_text(record.extracted_facts)]
    elif cls=='CompanyLead':
        parts=[record.summary,record.match_summary,record.evidence,_clean_text(record.company_intel)]
    elif cls=='Contact':
        parts=[record.title,record.company_summary,record.notes,_clean_text(record.company_intel)]
    else:
        parts=[getattr(record,f,'') for f in ('title','company','summary','description','match_summary','company_summary','name','email')]
    if include_campaign:
        hint=_campaign_hint(record)
        if hint:
            parts.append('Campaign hint: '+hint)
    return ' '.join(str(x or '') for x in parts)[:8000]


def _campaign_hint(record) -> str:
    try:
        campaign=getattr(record,'origin_campaign',None)
        if not campaign:
            return ''
        parts=[]
        for field in ('name','template','role_families','technologies'):
            val=str(getattr(campaign,field,'') or '').strip()
            if val:
                parts.append(val)
        return ' · '.join(parts)[:700]
    except Exception:
        return ''


def _namespace_for_model(model_or_record) -> str:
    name=model_or_record.__name__ if isinstance(model_or_record,type) else model_or_record.__class__.__name__
    return _NAMESPACE_BY_MODEL.get(name,name.casefold())



def _label_for_namespace(label: str, namespace: str) -> str:
    clean=_sanitize_focus_label(label) if '_sanitize_focus_label' in globals() else str(label or '').strip()
    ns=str(namespace or '').strip()
    if ns in {'hidden_leads','address_book'}:
        folded=clean.casefold()
        if folded in _COMPANY_NAMESPACE_LABEL_REWRITES:
            return _COMPANY_NAMESPACE_LABEL_REWRITES[folded]
        # Role-function buckets from Opportunities should not be created verbatim in
        # company/contact namespaces. Prefer a company-domain wording or leave blank.
        if folded in _OPPORTUNITY_ONLY_FOCUS_LABELS:
            return ''
    return clean


def _sanitize_focus_label_ns(value: str, namespace: str) -> str:
    base=_sanitize_focus_label(value)
    if not base:
        return ''
    return _label_for_namespace(base, namespace)


def _normalize_token(token: str) -> str:
    t=str(token or '').casefold().strip("._-–—,:;()[]{}'\"")
    if t in {'.net','net'}:
        return 'dotnet'
    if t in {'c++','cpp','cplusplus'}:
        return 'cplusplus'
    if t in {'c#','csharp'}:
        return 'csharp'
    if t in {'node.js','nodejs'}:
        return 'nodejs'
    if t in {'ai/ml','ml/ai'}:
        return 'ai'
    return t


def _ordered_tokens(text: str, *, keep_generic=False) -> list[str]:
    raw=re.findall(r'[a-z0-9+#.][a-z0-9+#.\-]{1,30}',str(text or '').casefold())
    out=[]
    for w in raw:
        t=_normalize_token(w)
        if len(t)<2 or t in _STOP or re.fullmatch(r'\d+\+?', t):
            continue
        if not keep_generic and t in _LABEL_GENERIC_TOKENS:
            continue
        out.append(t)
    return out


def _tokens(text: str) -> set[str]:
    return set(_ordered_tokens(text, keep_generic=True)) - _STOP


def _title_token(token: str) -> str:
    special={'iot':'IoT','ai':'AI','ml':'ML','api':'API','apis':'APIs','ui':'UI','ux':'UX','qa':'QA','sre':'SRE','devops':'DevOps','aws':'AWS','gcp':'GCP','azure':'Azure','linux':'Linux','unix':'Unix','rtos':'RTOS','qemu':'QEMU','bios':'BIOS','uefi':'UEFI','sdk':'SDK','ios':'iOS','macos':'macOS','gpu':'GPU','fpga':'FPGA','rf':'RF','sdio':'SDIO','usb':'USB','ble':'BLE','nfc':'NFC','crm':'CRM','erp':'ERP','soc':'SOC','siem':'SIEM','edr':'EDR','xdr':'XDR','dotnet':'.NET','cplusplus':'C++','csharp':'C#','nodejs':'Node.js'}
    return special.get(token, token[:1].upper()+token[1:])


def _label_from_tokens(tokens: list[str]) -> str:
    cleaned=[]
    for t in tokens:
        t=_normalize_token(t)
        if not t or t in _STOP:
            continue
        cleaned.append(t)
    dedup=[]
    for t in cleaned:
        if not dedup or dedup[-1] != t:
            dedup.append(t)
    cleaned=dedup
    key=' '.join(cleaned[:4]).casefold()
    if key in _CANONICAL_LABEL_REWRITES:
        return _CANONICAL_LABEL_REWRITES[key]
    joined=' '.join(cleaned).casefold()
    if 'buildroot' in cleaned or 'yocto' in cleaned:
        return 'Embedded Linux'
    if 'qemu' in cleaned or 'emulation' in cleaned or 'emulator' in cleaned:
        return 'Systems Emulation'
    if 'tls' in cleaned and ('security' in cleaned or 'network' in cleaned):
        return 'Network Security'
    if cleaned[:2] in (['reverse','engineering'], ['reverse','engineer']) or ('reverse' in cleaned and ('binary' in cleaned or 'protocol' in cleaned)):
        return 'Reverse Engineering'
    # Strip generic role/form words from the ends. Keep inner words like "Software"
    # only when paired with a distinctive domain token such as Embedded.
    while cleaned and cleaned[-1] in _LABEL_GENERIC_TOKENS:
        cleaned.pop()
    while cleaned and cleaned[0] in _LABEL_GENERIC_TOKENS:
        cleaned.pop(0)
    if not cleaned:
        return ''
    return ' '.join(_title_token(t) for t in cleaned[:4])



# Broad companion nouns are useful in labels, but they must not be enough to
# justify a label by themselves.  This list is intentionally label-agnostic: it
# applies to any proposed Focus name so small clusters cannot be named from a
# weak tail word such as "computing", "infrastructure", or "systems" while the
# actual subject/modifier word is absent from the records.
_LABEL_WEAK_HEAD_NOUNS = {
    'computing','infrastructure','systems','system','software','platform','platforms',
    'technology','technologies','engineering','engineer','development','developer',
    'services','service','solutions','solution','tools','tooling','products','product',
    'applications','application','operations','operation','companies','company',
}
_ACRONYM_LABEL_TOKENS = {'ai','ml','qa','it','iot','ui','ux','api','sre'}
_ACRONYM_EXPANSIONS = {
    'ai': ('artificial intelligence',),
    'ml': ('machine learning',),
    'qa': ('quality assurance',),
    'it': ('information technology',),
    'iot': ('internet of things',),
    'ui': ('user interface',),
    'ux': ('user experience',),
    'api': ('application programming interface',),
    'sre': ('site reliability engineering',),
}
_FOCUS_TOKEN_SYNONYMS = {
    # Display terminology avoids the vague "retro" bucket while still recognizing
    # explicit source evidence that uses the older/common vocabulary.
    'vintage': ('retro', 'classic', 'obsolete', 'legacy'),
}


def _distinctive_label_tokens(label: str) -> set[str]:
    return {
        t for t in _ordered_tokens(label,keep_generic=True)
        if t not in _LABEL_GENERIC_TOKENS and (len(t)>=3 or t in _ACRONYM_LABEL_TOKENS)
    }


def _anchor_label_tokens(label: str) -> set[str]:
    """Return the proposed label's required subject/modifier tokens.

    This is the general evidence gate for Focus names.  A label like
    "X Infrastructure" or "Y Computing" must be backed by X/Y in the record;
    the broad noun alone is not sufficient.  There are no label-specific
    prerequisite keyword lists here.
    """
    toks=_distinctive_label_tokens(label)
    anchors={t for t in toks if t not in _LABEL_WEAK_HEAD_NOUNS}
    return anchors or toks


def _token_supported_by_text(token: str, record_tokens: set[str], text_l: str) -> bool:
    token=_normalize_token(token)
    if not token:
        return False
    if token in record_tokens:
        return True
    # Support common acronym labels through their plain-language expansion, but
    # do not treat adjacent technologies as proof of the acronym.
    for phrase in _ACRONYM_EXPANSIONS.get(token,()):
        if re.search(r'(?<![a-z0-9])'+re.escape(phrase)+r'(?![a-z0-9])', text_l, flags=re.I):
            return True
    for synonym in _FOCUS_TOKEN_SYNONYMS.get(token,()):
        if _normalize_token(synonym) in record_tokens or re.search(r'(?<![a-z0-9])'+re.escape(synonym)+r'(?![a-z0-9])', text_l, flags=re.I):
            return True
    if '-' in token:
        spaced=token.replace('-',' ')
        if spaced in text_l:
            return True
    return False


def _is_generic_label(value: str) -> bool:
    label=' '.join(str(value or '').replace('/',' and ').replace('\\',' and ').replace('|',' and ').split())
    folded=label.casefold().strip()
    if _MALFORMED_LABEL_RE.search(label) or any(x in folded for x in _MALFORMED_LABEL_PHRASES):
        return True
    if folded in _USEFUL_EXACT_LABELS:
        return False
    if folded in _CANONICAL_LABEL_REWRITES:
        return not bool(_CANONICAL_LABEL_REWRITES[folded])
    if not folded or folded in _GENERIC_LABELS:
        return True
    toks=_ordered_tokens(label,keep_generic=True)
    distinctive=[t for t in toks if t not in _LABEL_GENERIC_TOKENS and t not in _STOP]
    if not distinctive:
        return True
    if len(distinctive)==1 and distinctive[0] in {'embedded','firmware','cloud','application','technology','technical','software','hardware','writing','legacy','cplusplus','protocol','security'}:
        return True
    # One weak domain word plus a generic role word is usually a search role, not a
    # useful Focus group. It can be refined by phrase extraction instead.
    if len(distinctive)==1 and any(t in _LABEL_GENERIC_TOKENS for t in toks):
        if distinctive[0] in {'firmware','cloud','application','software','platform','system','systems','technology','technical'}:
            return True
    if len(toks)<=2 and all(t in _LABEL_GENERIC_TOKENS or t in {'cloud','application','software','platform','technology'} for t in toks):
        return True
    return False


def _sanitize_focus_label(value: str) -> str:
    """Normalize an AI/dynamic label without accepting generic role buckets."""
    text=' '.join(str(value or '').replace('/',' and ').replace('\\',' and ').replace('|',' and ').split())
    text=re.sub(r'(?i)\s+&\s+',' and ',text)
    text=re.sub(r'(?i)\band\s+and\b','and',text)
    text=_CAMPAIGN_PREFIX_RE.sub('',text)
    text=re.sub(r'^[\-–—:;,\.\s]+|[\-–—:;,\.\s]+$','',text)
    if _MALFORMED_LABEL_RE.search(text) or any(x in text.casefold() for x in _MALFORMED_LABEL_PHRASES):
        return ''
    words=text.split()
    if len(words)>5:
        text=' '.join(words[:5])
    folded=text.casefold().strip()
    if folded in _CANONICAL_LABEL_REWRITES:
        text=_CANONICAL_LABEL_REWRITES[folded]
    if not text or len(text)>72 or _is_generic_label(text):
        return ''
    return text


def _comparison_budget(target: int, seed: int) -> int:
    """Stable target inside the documented internal ±20% operating range."""
    target=max(25,min(500,int(target or 100)))
    pct=0.80 + ((abs(int(seed or 0))*37) % 41)/100.0
    return max(1,min(600,int(round(target*pct))))


def _soft_group_cap(target: int) -> int:
    return max(1,int(math.ceil(max(5,min(30,int(target or 15)))*1.20)))


def _min_group_size(total: int) -> int:
    total=int(total or 0)
    # A minimum of 6-7 records was too strict for niche corpora and left most rows
    # unclassified. Keep singleton labels out of normal lists, but allow 2-3 item
    # specialist clusters so Focus remains useful.
    if total < 10:
        return 1
    # Two supporting records are enough to form a useful residual Focus. Requiring
    # three in mid-sized corpora left too many obvious topics in Unclassified.
    return 2


def _max_group_size(total: int, max_groups: int) -> int:
    total=max(1,int(total or 1)); max_groups=max(5,min(30,int(max_groups or 15)))
    average=total/max(1,max_groups)
    return max(_min_group_size(total)*2, min(int(math.ceil(total*0.32)), int(math.ceil(average*2.5))))


def _group_can_accept(label: str, current_count: int, total: int, max_groups: int, *, similarity: float=0.0) -> bool:
    if total < 40:
        return True
    cap=_max_group_size(total,max_groups)
    if int(current_count or 0) < cap:
        return True
    # Only exceptionally similar records can enter an already-large group.
    return float(similarity or 0.0) >= 0.42


def _sample_rows(model, exclude_pk, budget: int):
    fields=['pk','focus']
    name=model.__name__
    if name=='Opportunity': fields += ['title','company','list_highlight','description','raw_search_snippet','recommendation_reason','extracted_facts','origin_campaign']
    elif name=='CompanyLead': fields += ['company','summary','match_summary','evidence','contact_name','company_intel','origin_campaign']
    elif name=='Contact': fields += ['company','title','company_summary','name','email','notes','company_intel']
    qs=_active_focus_queryset(model).exclude(pk=exclude_pk).exclude(focus='').exclude(focus=FOCUS_UNCLASSIFIED).order_by('-pk').only(*[f for f in fields if f!='origin_campaign'])
    raw=list(qs[:max(budget,min(600,budget*2))])
    if len(raw)<=budget:
        return raw
    chosen=[]; seen=set()
    for row in raw:
        key=str(getattr(row,'focus','') or '')
        if key and key not in seen:
            chosen.append(row); seen.add(key)
            if len(chosen)>=budget: return chosen
    used={r.pk for r in chosen}
    for row in raw:
        if row.pk in used: continue
        chosen.append(row)
        if len(chosen)>=budget: break
    return chosen


def _local_focus_model() -> str:
    """Resolve an enabled local model without ever falling through to Cloud AI."""
    from portal.models import AIProviderConfig
    from portal.services import ollama
    cfg=AIProviderConfig.objects.filter(provider='ollama',enabled=True).first()
    if not cfg:
        return ''
    configured=str(getattr(cfg,'default_model','') or '').strip()
    if configured:
        return configured
    try:
        models=ollama.list_models() or []
        names=[str(x.get('name') or x.get('model') or '').strip() for x in models if isinstance(x,dict)]
        return next((x for x in names if x),'')
    except Exception:
        return ''


def _extract_json(text):
    raw=str(text or '').strip()
    if raw.startswith('```'):
        raw=re.sub(r'^```(?:json)?\s*','',raw,flags=re.I); raw=re.sub(r'\s*```$','',raw)
    try:
        return json.loads(raw)
    except Exception:
        m=re.search(r'(\{.*\}|\[.*\])',raw,re.S)
        if m:
            try: return json.loads(m.group(1))
            except Exception: pass
    return None


def _row_field_text(record, fields: tuple[str,...]) -> str:
    return ' '.join(str(getattr(record,f,'') or '') for f in fields)



def _topic_rule_candidates(title_text: str, body_text: str, campaign_hint: str='', namespace: str='opportunities') -> list[tuple[str,float,str]]:
    # Deterministic topic rules must be triggered by the record itself.  The campaign
    # that discovered a row is deliberately excluded here; otherwise a campaign such as
    # "Embedded Jobs" makes unrelated QA/support/backend roles look like Embedded Firmware.
    # campaign_hint remains in the signature for backward compatibility with callers, but
    # campaign-supported naming is handled separately in _candidate_phrases after checking
    # that the row contains the campaign's distinctive terms.
    blob=' '.join(str(x or '') for x in (title_text, body_text))[:12000]
    blob_l=blob.casefold()
    title_l=str(title_text or '').casefold()
    qa_role=bool(re.search(r'\b(?:qa|quality\s+assurance|test(?:er|\s+engineer))\b', title_l))
    out=[]
    seen=set()
    rules = _COMPANY_TOPIC_RULES if str(namespace or '') in {'hidden_leads','address_book'} else _TOPIC_RULES
    for label,patterns in rules:
        hits=0
        for pattern in patterns:
            if re.search(pattern, blob_l, flags=re.I):
                hits+=1
        if not hits:
            continue
        # A QA/Test role can mention payments, banking or another product domain as the
        # system under test.  Keep the functional QA Focus from being replaced by a
        # domain-engineering label solely because that product vocabulary appears.
        if qa_role and label=='FinTech Engineering':
            continue
        # Security + firmware and security + blockchain deserve the more specific label.
        if label=='Embedded Firmware' and re.search(r'\b(?:security|reverse|vulnerab|exploit)\b', blob_l) and re.search(r'\bfirmware\b', blob_l):
            label='Firmware Security'
        if label=='Network Security' and re.search(r'\bblockchain\b|\bsmart\s+contract\b', blob_l):
            label='Blockchain Security'
        key=label.casefold()
        if key in seen:
            continue
        seen.add(key)
        title_bonus=1.2 if re.search('|'.join(patterns), str(title_text or '').casefold(), flags=re.I) else 0.0
        out.append((label, 5.0 + min(3,hits)*0.8 + title_bonus, 'topic_rule'))
    return out

def _candidate_phrases(record, *, include_existing_label=False) -> list[tuple[str,float,str]]:
    """Return Focus label candidates derived from this row's own content.

    Campaign phrases get a small boost only when at least one distinctive campaign token
    is present in the non-campaign row text. That restores the original naming flavour
    without letting a campaign name assign unrelated records.
    """
    cls=record.__class__.__name__
    namespace=_namespace_for_model(record)
    if cls=='Opportunity':
        title_text=_row_field_text(record,('title',))
        body_text=_record_text(record,include_campaign=False)
    elif cls=='CompanyLead':
        title_text=_row_field_text(record,('summary',))
        body_text=_record_text(record,include_campaign=False)
    elif cls=='Contact':
        title_text=_row_field_text(record,('title','company_summary'))
        body_text=_record_text(record,include_campaign=False)
    else:
        title_text=_record_text(record,include_campaign=False)[:500]
        body_text=_record_text(record,include_campaign=False)
    row_tokens=set(_ordered_tokens(body_text,keep_generic=True))
    cands=[]

    def add(label, score, source):
        clean=_sanitize_focus_label_ns(label, namespace)
        if clean:
            cands.append((clean,float(score),source))

    for label,score,source in _topic_rule_candidates(title_text, body_text, _campaign_hint(record), namespace):
        add(label, score, source)

    if include_existing_label:
        add(getattr(record,'focus','') or '', 1.0, 'existing')

    # Campaign-inspired names. Require content support; do not accept campaign alone.
    hint=_campaign_hint(record)
    segments=[seg.strip() for seg in re.split(r'[·;,]+', _CAMPAIGN_PREFIX_RE.sub('',hint)) if seg.strip()]
    for seg in segments[:18]:
        seg=_CAMPAIGN_PREFIX_RE.sub('',seg)
        hint_tokens=_ordered_tokens(seg,keep_generic=True)
        hint_dist=[t for t in hint_tokens if t not in _LABEL_GENERIC_TOKENS and t not in _STOP]
        if hint_dist and row_tokens.intersection(hint_dist):
            add(_label_from_tokens(hint_tokens), 3.5, 'campaign_supported')
            meaningful_body=[t for t in _ordered_tokens(title_text+' '+body_text,keep_generic=False) if t not in hint_dist][:8]
            if len(hint_dist)==1 and meaningful_body:
                for extra in meaningful_body[:4]:
                    if extra!=hint_dist[0]:
                        add(_label_from_tokens([extra,hint_dist[0]]), 3.2, 'campaign_refined')
                        add(_label_from_tokens([hint_dist[0],extra]), 3.0, 'campaign_refined')

    # Title/summary-derived labels carry more signal than deep body text.
    title_tokens=_ordered_tokens(title_text,keep_generic=True)
    add(_label_from_tokens(title_tokens), 3.0, 'title')
    title_meaningful=[t for t in title_tokens if t not in _LABEL_GENERIC_TOKENS]
    if len(title_meaningful)>=2:
        for n in (3,2):
            for i in range(0,max(0,len(title_meaningful)-n+1)):
                add(_label_from_tokens(title_meaningful[i:i+n]), 2.7, 'title_ngram')

    # Ordered content n-grams. Consecutive meaningful phrases become candidate labels;
    # generic one/two-word role labels are rejected by _sanitize_focus_label.
    body_tokens=_ordered_tokens(body_text,keep_generic=False)
    seen_window=0
    for n,base in ((3,1.9),(2,1.7)):
        for i in range(0,max(0,len(body_tokens)-n+1)):
            window=body_tokens[i:i+n]
            if len(set(window))<len(window):
                continue
            add(_label_from_tokens(window), base, 'content_ngram')
            seen_window+=1
            if seen_window>=80:
                break
        if seen_window>=80:
            break
    # Strong single-topic fallback only for obviously specific terms; this is last-ranked
    # and will be used only if it has enough same-list support.
    for t in body_tokens[:80]:
        if len(t)>=6 and t not in _LABEL_GENERIC_TOKENS and t not in {'firmware','cloud','software','system','systems','platform','application','technology','writing','legacy','protocol','security','cplusplus'}:
            add(_label_from_tokens([t]), 0.7, 'content_token')

    # Deduplicate keeping highest score and earliest source.
    best={}
    for label,score,source in cands:
        key=label.casefold()
        if key not in best or score>best[key][1]:
            best[key]=(label,score,source)
    ranked=sorted(best.values(), key=lambda x:(-x[1], x[0].casefold()))
    return ranked[:24]


def _ai_choose_focus(text: str, existing_names, *, max_groups: int, campaign_hint: str='', total: int=0, namespace: str='opportunities') -> str:
    """Ask Local AI to choose/create one natural Focus label."""
    from portal.services import ollama
    model=_local_focus_model()
    if not model:
        return ''
    existing=[_sanitize_focus_label_ns(x, namespace) for x in existing_names] if 'namespace' in locals() else [_sanitize_focus_label(x) for x in existing_names]
    existing=[x for x in existing if x]
    # Avoid singleton churn in established lists. New labels in large corpora are formed
    # by batch repair where enough records can support the label.
    allow_new=len(existing)<_soft_group_cap(max_groups) and int(total or 0)<40
    prompt=(
        'Classify one ScoutBox record into a concise content Focus. Focus is the actual subject/domain of the record, not the campaign that found it. '
        'Use an existing focus when it fits. '+('You may create one new focus if none fits and the label is clearly supported by the record. ' if allow_new else 'You must use one existing focus; otherwise return an empty focus. ')+
        'A label must be a natural specific subject of 1-4 words. Reject generic role labels such as Application Engineer, Software Engineer, Engineer, Developer, Platform, or Cloud Technology. '
        'Do not use the vague label Retro Computing or any label containing Retro. Use Vintage Systems only when the record itself explicitly concerns vintage/classic/obsolete computers, legacy hardware platforms, old-system emulation/compatibility, DOS-era systems, or hardware restoration. '
        'Campaign is only weak naming inspiration and cannot override the record content. Return JSON only: {"focus":"..."}.\n'
        f'Existing focuses for this list only: {json.dumps(existing[:40],ensure_ascii=False)}\n'
        f'Campaign hint: {campaign_hint[:160]}\n'
        f'Record: {text[:4200]}'
    )
    try:
        answer,_=ollama.generate(prompt,model=model,stage='focus_classification',timeout=75,max_output_tokens=120,metadata_extra={'automatic':True,'focus_classification':True})
        payload=_extract_json(answer)
        label=_sanitize_focus_label_ns(payload.get('focus') if isinstance(payload,dict) else '', namespace)
        if not label:
            return ''
        if not allow_new and existing:
            folded={x.casefold():x for x in existing}
            return folded.get(label.casefold(),'')
        return label
    except Exception:
        return ''


def _record_supports_focus_label(record, label: str, *, similarity: float=0.0) -> bool:
    """Return whether this row itself supports a proposed Focus label.

    This is deliberately dynamic: support is derived from the proposed label's own
    distinctive words and the row's content, not from a hard-coded per-label keyword
    prerequisite list. Local AI may create/refine labels, but deterministic assignment
    still refuses labels whose own subject words have no footprint in the row.
    """
    clean=_sanitize_focus_label_ns(label, _namespace_for_model(record))
    if not clean:
        return False
    label_tokens=_distinctive_label_tokens(clean)
    if not label_tokens:
        return False
    anchor_tokens=_anchor_label_tokens(clean)
    text=_record_text(record,include_campaign=False)
    text_l=text.casefold()
    record_tokens=set(_ordered_tokens(text,keep_generic=True))
    supported_anchors={t for t in anchor_tokens if _token_supported_by_text(t, record_tokens, text_l)}
    if not supported_anchors:
        # High peer similarity can keep broad labels such as "Systems Software"
        # together, but it cannot make an unsupported specific modifier stick.
        return float(similarity or 0.0) >= 0.52 and anchor_tokens==label_tokens
    folded=clean.casefold()
    if folded and folded in text_l:
        return True
    supported={t for t in label_tokens if _token_supported_by_text(t, record_tokens, text_l)}
    coverage=len(supported)/max(1,len(label_tokens))
    anchor_coverage=len(supported_anchors)/max(1,len(anchor_tokens))
    # Short labels need stronger lexical support; longer labels can be supported by
    # their distinctive subject/modifier words. The requirement scales from the
    # proposed label instead of using fixed prerequisites for named Focus groups.
    if len(label_tokens)<=2:
        return anchor_coverage>=1.0 and coverage>=0.50
    return anchor_coverage>=0.50 and (coverage>=0.34 or float(similarity or 0.0)>=0.42)


def _peer_similarity_choice(record, samples):
    tokens=set(_ordered_tokens(_record_text(record,include_campaign=False),keep_generic=False))
    if not tokens:
        return '',0.0
    by_focus=defaultdict(float)
    for peer in samples:
        focus=_sanitize_focus_label(getattr(peer,'focus',''))
        if not focus:
            continue
        # Generic labels should not continue to attract new records. They will be repaired
        # by the batch balancer instead.
        if _is_generic_label(focus):
            continue
        other=set(_ordered_tokens(_record_text(peer,include_campaign=False),keep_generic=False))
        if not other:
            continue
        overlap=len(tokens & other)
        if not overlap:
            continue
        score=overlap/max(3.0,math.sqrt(len(tokens)*len(other)))
        by_focus[focus]=max(by_focus[focus],score)
    if not by_focus:
        return '',0.0
    ranked=sorted(by_focus.items(), key=lambda kv: kv[1], reverse=True)
    label,score=ranked[0]
    if len(ranked)>1 and score < ranked[1][1]*1.18:
        return '',float(score)
    return label,float(score)


def _focus_metadata_target(record):
    cls=record.__class__.__name__
    if cls=='Opportunity' and hasattr(record,'extracted_facts'):
        return 'extracted_facts'
    if cls in {'CompanyLead','Contact'} and hasattr(record,'company_intel'):
        return 'company_intel'
    return ''


def _write_focus_assignment(record, focus: str, *, source: str, confidence: int=0, reason: str='') -> None:
    updates={'focus':focus}
    field=_focus_metadata_target(record)
    if field:
        payload=getattr(record,field,None)
        if isinstance(payload,dict):
            payload=dict(payload)
        else:
            payload={}
        payload['focus_assignment']={
            'namespace':_namespace_for_model(record),
            'source':str(source or 'unknown'),
            'confidence':max(0,min(100,int(confidence or 0))),
            'reason':str(reason or '')[:300],
            'assigned_at':timezone.now().isoformat(),
            'release':FOCUS_TARGET_VERSION,
        }
        updates[field]=payload
        setattr(record,field,payload)
    record.__class__.objects.filter(pk=record.pk).update(**updates)
    record.focus=focus


def _active_focus_queryset(model):
    qs=model.objects.all()
    fields={f.name for f in model._meta.fields}
    if 'user_deleted' in fields:
        qs=qs.filter(user_deleted=False)
    if 'suppressed' in fields:
        qs=qs.filter(suppressed=False)
    if 'deleted_at' in fields:
        qs=qs.filter(deleted_at__isnull=True)
    return qs


def _existing_focus_counts(model) -> dict[str,int]:
    rows=_active_focus_queryset(model).exclude(focus='').exclude(focus=FOCUS_UNCLASSIFIED).values('focus').annotate(n=Count('pk'))
    counts={}
    for row in rows:
        label=_sanitize_focus_label(row.get('focus'))
        if label:
            counts[label]=counts.get(label,0)+int(row.get('n') or 0)
    return counts


def classify_focus_detail(record, *, comparison_target=None, max_groups=None) -> dict:
    """Classify a new record using same-list content evidence only.

    Origin campaign is never a deterministic assignment source. It may inspire label
    wording when supported by record content, but if Local AI is unavailable and peer
    similarity is weak, the row stays blank/pending for a later same-list batch pass.
    """
    from portal.models import PortalSettings
    ps=PortalSettings.objects.get_or_create(pk=1)[0]
    comparison_target=int(comparison_target if comparison_target is not None else getattr(ps,'focus_comparison_records',100) or 100)
    max_groups=int(max_groups if max_groups is not None else getattr(ps,'max_focus_groups',15) or 15)
    model=record.__class__
    active_total=_active_focus_queryset(model).count()
    counts=_existing_focus_counts(model)
    budget=_comparison_budget(comparison_target,getattr(record,'pk',0) or 1)
    samples=_sample_rows(model,getattr(record,'pk',None),budget)
    peer_label,similarity=_peer_similarity_choice(record,samples[:budget])
    if peer_label and similarity>=0.22 and _record_supports_focus_label(record,peer_label,similarity=similarity) and _group_can_accept(peer_label,counts.get(peer_label,0),active_total,max_groups,similarity=similarity):
        return {'focus':peer_label,'source':'peer_similarity','confidence':min(96,int(round(similarity*100))),'reason':f'same-list content similarity {similarity:.3f}'}

    existing_names=[name for name,_ in sorted(counts.items(), key=lambda kv:(-kv[1],kv[0].casefold()))]
    proposed=_ai_choose_focus(_record_text(record,include_campaign=False),existing_names,max_groups=max_groups,campaign_hint=_campaign_hint(record),total=active_total,namespace=_namespace_for_model(record))
    if proposed and (proposed not in counts or _group_can_accept(proposed,counts.get(proposed,0),active_total,max_groups,similarity=similarity)):
        return {'focus':proposed,'source':'local_ai','confidence':82,'reason':'Local AI selected a same-list content focus.'}

    # Established corpora should not grow singleton labels through per-row fallback. For
    # small lists, a content-supported dynamic label keeps Focus useful before Local AI is
    # available.
    if active_total<20:
        for label,score,source in _candidate_phrases(record):
            return {'focus':label,'source':'dynamic_label','confidence':68,'reason':f'{source} label supported by row content.'}

    if peer_label and similarity>=0.42 and _group_can_accept(peer_label,counts.get(peer_label,0),active_total,max_groups,similarity=similarity):
        return {'focus':peer_label,'source':'strong_peer_similarity','confidence':min(94,int(round(similarity*100))),'reason':f'strong same-list content similarity {similarity:.3f}'}
    return {'focus':'','source':'pending','confidence':0,'reason':'No sufficiently supported balanced Focus assignment yet.'}


def classify_focus(record, *, comparison_target=None, max_groups=None) -> str:
    return str(classify_focus_detail(record,comparison_target=comparison_target,max_groups=max_groups).get('focus') or '')


def assign_focus(record, *, force=False) -> str:
    current=str(getattr(record,'focus','') or '').strip()
    if current and current!=FOCUS_UNCLASSIFIED and not force:
        return current
    detail=classify_focus_detail(record)
    focus=str(detail.get('focus') or '').strip()
    if focus:
        _write_focus_assignment(
            record,
            focus,
            source=str(detail.get('source') or 'unknown'),
            confidence=int(detail.get('confidence') or 0),
            reason=str(detail.get('reason') or ''),
        )
        return focus
    return current if current==FOCUS_UNCLASSIFIED else ''


def focus_options(queryset):
    rows=queryset.order_by().values('focus').annotate(n=Count('pk',distinct=True)).order_by('-n','focus')
    counts=defaultdict(int)
    for row in rows:
        value=str(row.get('focus') or FOCUS_UNCLASSIFIED).strip() or FOCUS_UNCLASSIFIED
        clean=_sanitize_focus_label(value)
        if not clean or value.casefold()==FOCUS_UNCLASSIFIED.casefold():
            value=FOCUS_UNCLASSIFIED
        else:
            value=clean
        counts[value]+=int(row.get('n') or 0)
    return [{'value':value,'label':value,'count':count} for value,count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].casefold()))]


def _label_similarity(a: str, b: str) -> float:
    ta=_distinctive_label_tokens(a); tb=_distinctive_label_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb)/max(1.0,math.sqrt(len(ta)*len(tb)))


def _build_candidate_index(records, *, include_existing=False):
    per_record={}
    counts=Counter()
    weighted=Counter()
    sources=defaultdict(Counter)
    for r in records:
        cands=_candidate_phrases(r,include_existing_label=include_existing)
        per_record[int(r.pk)]=cands
        seen=set()
        for label,score,source in cands:
            key=label.casefold()
            if key not in seen:
                counts[label]+=1; seen.add(key)
            weighted[label]+=score
            sources[label][source]+=1
    return per_record,counts,weighted,sources


def _select_balanced_labels(records, max_groups: int, *, include_existing=False) -> list[str]:
    total=len(records)
    if total<=0:
        return []
    min_size=_min_group_size(total)
    per_record,counts,weighted,sources=_build_candidate_index(records,include_existing=include_existing)
    max_groups=max(3,_soft_group_cap(max_groups))
    candidates=[]
    for label,n in counts.items():
        if n < min_size:
            continue
        if _is_generic_label(label):
            continue
        # Reward campaign-supported names, but only after row-content support counted them.
        source_bonus=0.0
        if sources[label].get('campaign_supported'):
            source_bonus += 2.0
        if sources[label].get('campaign_refined'):
            source_bonus += 1.5
        if sources[label].get('title') or sources[label].get('title_ngram'):
            source_bonus += 1.0
        length_bonus=min(0.8,0.2*len(_distinctive_label_tokens(label)))
        score=float(n)*3.0 + float(weighted[label])*0.35 + source_bonus + length_bonus
        candidates.append((label,n,score))
    candidates.sort(key=lambda x:(-x[2],-x[1],x[0].casefold()))
    selected=[]
    for label,n,score in candidates:
        toks=_distinctive_label_tokens(label)
        if not toks:
            continue
        # Prefer the more specific phrase when two labels are nearly the same.
        replaced=False; too_close=False
        for idx,existing in enumerate(list(selected)):
            sim=_label_similarity(label,existing)
            if sim>=0.92:
                if len(toks)>len(_distinctive_label_tokens(existing)) and counts[label]>=max(min_size,counts[existing]*0.6):
                    selected[idx]=label; replaced=True
                else:
                    too_close=True
                break
        if too_close and not replaced:
            continue
        if not replaced:
            selected.append(label)
        if len(selected)>=max_groups:
            break
    return selected


def _assign_records_to_labels(records, labels: list[str], max_groups: int) -> dict[int,str]:
    if not records or not labels:
        return {}
    total=len(records); min_size=_min_group_size(total); max_size=_max_group_size(total,max_groups)
    selected={l.casefold():l for l in labels}
    counts=Counter()
    mapping={}
    # Assign high-confidence records first so capped groups fill with the best matches.
    row_choices=[]
    for r in records:
        choices=[]
        text_tokens=set(_ordered_tokens(_record_text(r,include_campaign=False),keep_generic=True))
        for label,score,source in _candidate_phrases(r,include_existing_label=True):
            canonical=selected.get(label.casefold())
            if not canonical:
                continue
            # Every assignment must be supported by this row's own content.  The
            # support test derives evidence dynamically from the proposed label; no
            # Focus name gets a hard-coded prerequisite keyword list.
            if not _record_supports_focus_label(r, canonical):
                continue
            choices.append((canonical,score,source))
        choices.sort(key=lambda x:(-x[1],x[0].casefold()))
        row_choices.append((r,choices))
    row_choices.sort(key=lambda item: (-(item[1][0][1] if item[1] else 0), int(item[0].pk)))
    for r,choices in row_choices:
        chosen=''
        for label,score,source in choices:
            if counts[label] < max_size:
                chosen=label; break
        if not chosen and choices:
            # Let a group exceed the soft cap only when there is no alternative. A later
            # quality pass can split it, but we avoid leaving obviously matching rows blank.
            chosen=choices[0][0]
        if chosen:
            mapping[int(r.pk)]=chosen; counts[chosen]+=1
    # Second pass: reduce excessive Unclassified rows by assigning records to an already-selected
    # balanced label when the selected label's distinctive tokens are clearly supported by
    # the row. This prevents blank-heavy taxonomies without creating singleton labels.
    if False and len(mapping) < int(total*0.86):
        label_tokens={label:_distinctive_label_tokens(label) for label in labels}
        for r in records:
            pk=int(r.pk)
            if pk in mapping:
                continue
            row_tokens=set(_ordered_tokens(_record_text(r,include_campaign=False),keep_generic=True))
            best=''; best_score=0.0
            for label,toks in label_tokens.items():
                if not toks:
                    continue
                overlap=len(row_tokens & toks)
                if not overlap:
                    continue
                score=overlap/max(1.0,len(toks))
                if counts[label] >= max_size and score < 0.75:
                    continue
                if score>best_score:
                    best_score=score; best=label
            if best and best_score>=0.50:
                mapping[pk]=best; counts[best]+=1
    # Third pass: for rows whose phrasing does not exactly produce the selected
    # label, compare against lightweight prototypes formed from already assigned
    # same-list records. This reduces huge Unclassified buckets without creating
    # single-record labels.
    if False and len(mapping) < int(total*0.90):
        prototypes={label:set(_distinctive_label_tokens(label)) for label in labels}
        for r in records:
            label=mapping.get(int(r.pk))
            if not label:
                continue
            toks=[t for t in _ordered_tokens(_record_text(r,include_campaign=False),keep_generic=False) if t not in _LABEL_GENERIC_TOKENS]
            for t,n in Counter(toks).most_common(14):
                if len(t)>=4:
                    prototypes[label].add(t)
        for r in records:
            pk=int(r.pk)
            if pk in mapping:
                continue
            row_tokens=set(_ordered_tokens(_record_text(r,include_campaign=False),keep_generic=False))
            if not row_tokens:
                continue
            best=''; best_score=0.0
            for label,proto in prototypes.items():
                if not proto:
                    continue
                overlap=len(row_tokens & proto)
                if not overlap:
                    continue
                score=overlap/max(4.0,math.sqrt(len(row_tokens)*len(proto)))
                if counts[label] >= max_size and score < 0.20:
                    continue
                if score>best_score:
                    best_score=score; best=label
            threshold=0.095 if len(mapping) < int(total*0.70) else 0.12
            if best and best_score>=threshold:
                mapping[pk]=best; counts[best]+=1

    # Fourth pass: fill useful residual rows from their own strongest selected
    # candidate when the assignment is rule/title supported. This targets the
    # 10-15% Unclassified ceiling without creating new singleton groups or using
    # campaign dominance.
    if False and len(mapping) < int(total*0.86):
        for r in records:
            pk=int(r.pk)
            if pk in mapping:
                continue
            best=''; best_score=0.0
            for label,score,source in _candidate_phrases(r,include_existing_label=False):
                canonical=selected.get(label.casefold())
                if not canonical:
                    continue
                if source not in {'topic_rule','title','title_ngram','campaign_supported','campaign_refined'} and score < 2.7:
                    continue
                if counts[canonical] >= max_size and score < 5.0:
                    continue
                if score>best_score:
                    best_score=score; best=canonical
            if best and best_score>=2.7:
                mapping[pk]=best; counts[best]+=1

    # Merge/clear groups that ended up too small, except on small corpora.
    if min_size>1:
        small={label for label,n in counts.items() if n<min_size}
        if small:
            stable=[label for label,n in counts.items() if n>=min_size and label not in small]
            for pk,label in list(mapping.items()):
                if label not in small:
                    continue
                best=''; best_sim=0.0
                for dest in stable:
                    sim=_label_similarity(label,dest)
                    if sim>best_sim:
                        best_sim=sim; best=dest
                if best and best_sim>=0.34:
                    mapping[pk]=best; counts[best]+=1
                else:
                    mapping.pop(pk,None)
    return mapping


def _batch_ai_assign(model, records, existing_names, max_groups):
    """Classify an upgrade batch with Local AI. Every record in the batch gets a result."""
    from portal.services import ollama
    local_model=_local_focus_model()
    if not local_model:
        raise RuntimeError('No enabled local Ollama model is available for Focus taxonomy rebuild.')
    rows=[]
    for r in records:
        rows.append({'id':int(r.pk),'text':_record_text(r,include_campaign=False)[:1600],'campaign_hint':_campaign_hint(r)[:120]})
    namespace=_namespace_for_model(model)
    prompt=(
        'Create/assign ScoutBox Focus labels for these records in ONE list namespace only. Focus means the actual subject/domain represented by each record. ' +
        ('For company/contact namespaces, create company-domain or offering labels, not open-role job-function labels. ' if namespace in {'hidden_leads','address_book'} else '') + 'Use campaign names only as naming inspiration when the record content supports them. Reuse existing focuses whenever sensible. '
        'Keep the taxonomy precise: blank is better than a misleading label, avoid giant catch-all buckets, and avoid one-item labels except for tiny corpora. '
        'New labels must be natural specific subjects, 1-4 words, not generic role labels such as Application Engineer, Software Engineer, Engineer, Developer, Platform, or Cloud Technology. '
        'Do not use the vague label Retro Computing or any label containing Retro. Use Vintage Systems only for records with explicit vintage/classic/obsolete computer, legacy-hardware, old-system emulation/compatibility, DOS-era, or restoration evidence. '
        'For each non-empty focus, decide the required evidence dynamically from the label and this record; do not use any fixed keyword prerequisite list. '
        'Return JSON only in this exact shape: {"assignments":[{"id":123,"focus":"Natural label","evidence_terms":["term from record"],"confidence":0-100}, ...]}. Assign every supplied id. Use an empty focus for outliers that should stay pending.\n'
        f'Configured target maximum focus groups: {int(max_groups)}.\n'
        f'Existing focuses for this list only: {json.dumps(existing_names[:40],ensure_ascii=False)}\n'
        f'Records: {json.dumps(rows,ensure_ascii=False)}'
    )
    records_by_id={int(r.pk):r for r in records}
    answer,_=ollama.generate(prompt,model=local_model,stage='focus_taxonomy_rebuild',timeout=180,max_output_tokens=max(500,min(2400,90*len(rows))),metadata_extra={'automatic':True,'focus_taxonomy_rebuild':True,'focus_namespace':namespace})
    payload=_extract_json(answer)
    assignments={}
    if isinstance(payload,dict):
        for item in payload.get('assignments') or []:
            if not isinstance(item,dict): continue
            try: pk=int(item.get('id'))
            except Exception: continue
            label=_sanitize_focus_label_ns(item.get('focus'), namespace)
            try:
                conf=int(item.get('confidence') or 0)
            except Exception:
                conf=0
            evidence=item.get('evidence_terms') if isinstance(item,dict) else []
            has_evidence=bool(evidence)
            record=records_by_id.get(pk)
            if label and record is not None and (conf>=55 or has_evidence) and _record_supports_focus_label(record,label):
                assignments[pk]=label
    return assignments


def _stable_focus_names(model):
    rows=_active_focus_queryset(model).exclude(focus='').exclude(focus=FOCUS_UNCLASSIFIED).values('focus').annotate(n=Count('pk')).order_by('-n','focus')
    ns=_namespace_for_model(model)
    return [str(x['focus']) for x in rows if _sanitize_focus_label_ns(x.get('focus'), ns)]


def _build_model_focus_shadow(model, max_groups: int, *, progress=None, progress_offset=0, progress_total=None):
    """Build a complete balanced replacement mapping without touching live values."""
    records=list(_active_focus_queryset(model).order_by('pk'))
    total=len(records)
    namespace=_namespace_for_model(model)
    ai_seeded=False
    # AI-first rebuild: let Local AI propose namespace-specific labels and dynamic
    # evidence terms, then run deterministic balance/support checks over those labels.
    # This avoids hard-coded keyword prerequisites for named groups while still keeping
    # assignments conservative when a row does not support the generated label.
    if records and _local_focus_model():
        names=_stable_focus_names(model)
        done_ai=0
        while done_ai<len(records):
            batch=records[done_ai:done_ai+20]
            try:
                mappings=_batch_ai_assign(model,batch,names,max_groups)
            except Exception:
                break
            for r in batch:
                label=_sanitize_focus_label_ns(mappings.get(int(r.pk),''), namespace)
                if label:
                    r.focus=label
                    ai_seeded=True
                    if label.casefold() not in {x.casefold() for x in names}:
                        names.append(label)
            done_ai+=len(batch)
            if progress:
                progress(progress_offset+min(total,done_ai),progress_total if progress_total is not None else total)
    labels=_select_balanced_labels(records,max_groups,include_existing=True)
    shadow=_assign_records_to_labels(records,labels,max_groups)
    # If AI was not available, deterministic candidates still build a conservative
    # taxonomy.  There is intentionally no forced-coverage pass; blank is safer than
    # a misleading Focus group.
    if progress:
        progress(progress_offset+total,progress_total if progress_total is not None else total)
    group_count=len({x.casefold() for x in shadow.values() if x and x!=FOCUS_UNCLASSIFIED})
    if group_count>_soft_group_cap(max_groups):
        raise RuntimeError(f'Focus taxonomy rebuild proposed {group_count} groups, above the safe cap {_soft_group_cap(max_groups)}.')
    return shadow,{'total':total,'processed':total,'assigned':len(shadow),'groups':group_count,'namespace':_namespace_for_model(model),'balanced':True}


def rebuild_model_focus_with_ai(model, max_groups: int, *, progress=None):
    """Atomically rebuild one model taxonomy; live labels survive any failure."""
    shadow,stats=_build_model_focus_shadow(model,max_groups,progress=progress)
    with transaction.atomic():
        rows=list(_active_focus_queryset(model).select_for_update().only('pk','focus',_focus_metadata_field_for_model(model)))
        for row in rows:
            row.focus=shadow.get(int(row.pk),'')
        model.objects.bulk_update(rows,['focus'],batch_size=500)
    return stats


def _focus_metadata_field_for_model(model) -> str:
    name=model.__name__
    if name=='Opportunity':
        return 'extracted_facts'
    if name in {'CompanyLead','Contact'}:
        return 'company_intel'
    return 'focus'


def rebuild_all_focus_taxonomies_with_ai(max_groups: int, *, progress=None):
    from portal.models import Opportunity, CompanyLead, Contact
    models=[('opportunities',Opportunity),('hidden_leads',CompanyLead),('address_book',Contact)]
    total=sum(_active_focus_queryset(m).count() for _,m in models); offset=0; out={}; shadows={}
    for key,model in models:
        count=_active_focus_queryset(model).count()
        shadow,stats=_build_model_focus_shadow(model,max_groups,progress=progress,progress_offset=offset,progress_total=total)
        shadows[key]=(model,shadow); out[key]=stats
        offset+=count
    with transaction.atomic():
        for key,(model,shadow) in shadows.items():
            fields=['pk','focus']
            rows=list(_active_focus_queryset(model).select_for_update().only(*fields))
            for row in rows:
                row.focus=shadow.get(int(row.pk),'')
            model.objects.bulk_update(rows,['focus'],batch_size=500)
    out['total']=total
    return out


def focus_taxonomy_snapshot():
    """Return current per-list counts and quality hints."""
    from portal.models import Opportunity, CompanyLead, Contact
    out={}
    for key,model in (('opportunities',Opportunity),('hidden_leads',CompanyLead),('address_book',Contact)):
        qs=_active_focus_queryset(model)
        total=qs.count()
        classified_qs=qs.exclude(focus='').exclude(focus=FOCUS_UNCLASSIFIED)
        classified=classified_qs.count()
        group_rows=list(classified_qs.values('focus').annotate(n=Count('pk')).order_by('-n','focus'))
        groups=len(group_rows)
        top=group_rows[0] if group_rows else {}
        singleton=sum(1 for g in group_rows if int(g.get('n') or 0)==1)
        generic=[str(g.get('focus') or '') for g in group_rows if _is_generic_label(str(g.get('focus') or ''))]
        out[key]={
            'total':total,'classified':classified,'groups':groups,
            'top_focus':str(top.get('focus') or ''),'top_count':int(top.get('n') or 0),
            'singleton_groups':singleton,'generic_labels':generic[:8],
            'quality_warning': bool(total>=20 and ((top and int(top.get('n') or 0)>_max_group_size(total,15)) or singleton>max(2,groups//4) or generic)),
        }
    return out


def focus_taxonomy_rebuild_due(settings_row, *, now=None):
    """Queue a one-time background Focus quality rebuild after upgrade.

    Startup migrations only mark the version pending; the scheduler queues this as a
    normal Dashboard Activity job after web health is available.
    """
    version=str(getattr(settings_row,'focus_taxonomy_version','') or '').strip()
    state=dict(getattr(settings_row,'focus_taxonomy_state',{}) or {})
    pending=bool(state.get('v0113_focus_label_evidence_repair_pending')) or bool(state.get('v010118_focus_quality_repair_pending')) or version!=FOCUS_TARGET_VERSION
    reasons=[]
    if pending:
        if state.get('v0113_focus_label_evidence_repair_pending') or version!=FOCUS_TARGET_VERSION:
            reasons.append('focus_label_evidence_repair_v0113')
        elif state.get('v010118_focus_quality_repair_pending'):
            reasons.append('focus_quality_repair_v010118')
    return {'due':pending,'reasons':reasons,'snapshot':focus_taxonomy_snapshot(),'automatic_full_rebuild_disabled':False,'balanced_batch_repair_enabled':True,'target_version':FOCUS_TARGET_VERSION}


def repair_model_focus_taxonomy(model, target: int, *, rewrite=False, limit=None) -> dict:
    """Balanced same-list repair used by upgrade and blank backfill.

    When rewrite=True, all active rows in this namespace may be reassigned atomically.
    Otherwise only blank/Unclassified rows are filled, and existing labels remain stable.
    """
    target=max(5,min(30,int(target or 15)))
    qs=_active_focus_queryset(model).order_by('pk')
    all_records=list(qs[:int(limit)] if limit else qs)
    if not all_records:
        return {'namespace':_namespace_for_model(model),'total':0,'assigned':0,'groups':0,'rewrite':bool(rewrite)}
    labels=_select_balanced_labels(all_records,target,include_existing=not rewrite)
    mapping=_assign_records_to_labels(all_records,labels,target)
    if not rewrite:
        records=[r for r in all_records if not str(getattr(r,'focus','') or '').strip() or str(getattr(r,'focus','') or '').strip()==FOCUS_UNCLASSIFIED]
        allowed={int(r.pk) for r in records}
        mapping={pk:label for pk,label in mapping.items() if pk in allowed}
    now=timezone.now(); field=_focus_metadata_field_for_model(model)
    changed=[]
    for row in all_records:
        pk=int(row.pk)
        if rewrite:
            new=mapping.get(pk,'')
        else:
            if pk not in mapping:
                continue
            new=mapping.get(pk,'')
        old=str(getattr(row,'focus','') or '')
        if old==new:
            continue
        row.focus=new
        if field in {'extracted_facts','company_intel'}:
            payload=getattr(row,field,None)
            payload=dict(payload) if isinstance(payload,dict) else {}
            payload['focus_assignment']={
                'namespace':_namespace_for_model(model),
                'source':'balanced_batch_repair' if rewrite else 'balanced_blank_backfill',
                'previous_focus':old[:80],
                'confidence':74 if new else 0,
                'reason':'Balanced same-list Focus repair using record content and campaign-supported naming hints.',
                'assigned_at':now.isoformat(),
                'release':FOCUS_TARGET_VERSION,
            }
            setattr(row,field,payload)
        changed.append(row)
    if changed:
        update_fields=['focus']
        if field in {'extracted_facts','company_intel'}:
            update_fields.append(field)
        model.objects.bulk_update(changed,update_fields,batch_size=500)
    return {'namespace':_namespace_for_model(model),'total':len(all_records),'changed':len(changed),'assigned':sum(1 for x in mapping.values() if x),'groups':len(set(mapping.values())),'rewrite':bool(rewrite),'labels':labels[:30]}


def backfill_blank_focuses(limit_per_model=60) -> dict:
    """Classify blank/Unclassified rows in balanced same-list batches."""
    from portal.models import Opportunity, CompanyLead, Contact, PortalSettings
    ps=PortalSettings.objects.get_or_create(pk=1)[0]
    target=int(getattr(ps,'max_focus_groups',15) or 15)
    out={}
    for key,model in (('opportunities',Opportunity),('hidden_leads',CompanyLead),('address_book',Contact)):
        qs=_active_focus_queryset(model).filter(Q(focus='')|Q(focus=FOCUS_UNCLASSIFIED)).order_by('-pk')
        blank_total=qs.count()
        # Include a window of already-classified peers for label selection, but only blanks
        # are updated by repair_model_focus_taxonomy(rewrite=False).
        result=repair_model_focus_taxonomy(model,target,rewrite=False,limit=max(int(limit_per_model or 60)*4,100))
        result['blank_total']=int(blank_total)
        out[key]=result
    return out


def taxonomy_quality_repair_needed(model, target: int) -> bool:
    qs=_active_focus_queryset(model)
    total=qs.count()
    if total<20:
        return False
    rows=list(qs.exclude(focus='').exclude(focus=FOCUS_UNCLASSIFIED).values('focus').annotate(n=Count('pk')).order_by('-n','focus'))
    if not rows:
        return True
    top=int(rows[0].get('n') or 0)
    singleton=sum(1 for r in rows if int(r.get('n') or 0)==1)
    generic=any(_is_generic_label(str(r.get('focus') or '')) for r in rows)
    unclassified=total-sum(int(r.get('n') or 0) for r in rows)
    return top>_max_group_size(total,target) or singleton>max(2,len(rows)//4) or generic or (total>=100 and unclassified>max(12,int(total*0.15))) or (40<=total<100 and unclassified>max(10,int(total*0.25)))


def rebalance_focus_taxonomy_once(model, target: int) -> dict:
    """Run one bounded balanced repair for a list namespace when quality is poor."""
    if not taxonomy_quality_repair_needed(model,target):
        return {'namespace':_namespace_for_model(model),'changed':0,'reason':'quality-ok'}
    return repair_model_focus_taxonomy(model,target,rewrite=True)


def rebalance_focus_taxonomies_once(target: int) -> dict:
    from portal.models import Opportunity, CompanyLead, Contact
    return {
        'opportunities':rebalance_focus_taxonomy_once(Opportunity,target),
        'hidden_leads':rebalance_focus_taxonomy_once(CompanyLead,target),
        'address_book':rebalance_focus_taxonomy_once(Contact,target),
    }
