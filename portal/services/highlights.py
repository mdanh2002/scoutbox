import re


_GENERIC_PREFIXES = (
    'this role', 'this opportunity', 'the role', 'the opportunity',
    'the position', 'this position', 'the job', 'this job',
)

# Concrete role/JD signals. Level 3 = unusually specific subsystem/tool, level 2 =
# substantive target-domain signal, level 1 = broad supporting signal. The list
# summary is a terse concrete cue, not a prose synopsis.
_SIGNAL_PATTERNS = [
    (r'\bedk\s*ii\b|\bedk2\b', 'EDK II', 3, 'firmware'),
    (r'\bdxe\b|\bsmm\b|\bpei\b', 'UEFI DXE/SMM/PEI', 3, 'firmware'),
    (r'\bsecure boot\b|\bmeasured boot\b|\btpm\b', 'Secure/Measured Boot', 3, 'security'),
    (r'\bbmc\b|\bipmi\b|\bredfish\b', 'BMC/IPMI/Redfish', 3, 'firmware'),
    (r'\bacpi\b', 'ACPI', 3, 'firmware'),
    (r'\bpcie\b|\bpci express\b', 'PCIe', 3, 'firmware'),
    (r'\bcoreboot\b', 'coreboot', 3, 'firmware'),
    (r'\bu-boot\b|\bbootloader\b', 'U-Boot/bootloader', 3, 'firmware'),
    (r'\bboard bring[- ]?up\b|\bhardware bring[- ]?up\b', 'board bring-up', 3, 'embedded'),
    (r'\bjtag\b|\bswd\b', 'JTAG/SWD', 3, 'reverse'),
    (r'\bghidra\b|\bida pro\b|\bida\b', 'Ghidra/IDA', 3, 'reverse'),
    (r'\bwindbg\b|\bx64dbg\b', 'WinDbg/x64dbg', 3, 'reverse'),
    (r'\bbinary analys(?:is|t)\b', 'binary analysis', 3, 'reverse'),
    (r'\bfuzz(?:ing|er)\b', 'fuzzing', 3, 'security'),
    (r'\bexploit development\b', 'exploit development', 3, 'security'),
    (r'\bcve\b|\bvulnerability research(?:er)?\b|\bsecurity research(?:er)?\b', 'vulnerability/security research', 3, 'security'),
    (r'\bzephyr\b', 'Zephyr', 3, 'embedded'),
    (r'\bfreertos\b|\bfree rtos\b', 'FreeRTOS', 3, 'embedded'),
    (r'\bdspic\b|\bpic32\b|\bpic24\b', 'PIC/dsPIC', 3, 'embedded'),
    (r'\bstm32\b|\besp32\b', 'STM32/ESP32', 3, 'embedded'),
    (r'\bqemu\b.*\bkvm\b|\bkvm\b.*\bqemu\b', 'QEMU/KVM', 3, 'virtualization'),
    (r'\bqemu\b', 'QEMU', 3, 'virtualization'),
    (r'\bvirtio\b|\blibvirt\b', 'VirtIO/libvirt', 3, 'virtualization'),
    (r'\bfirecracker\b|\bgvisor\b|\bkata containers?\b', 'microVM/container isolation', 3, 'virtualization'),
    (r'\breverse engineer(?:ing|er)?\b', 'reverse engineering', 3, 'reverse'),
    (r'\bmalware analys(?:is|t)\b', 'malware analysis', 3, 'reverse'),
    (r'\bprotocol (?:reverse engineering|analysis)\b', 'protocol analysis', 3, 'reverse'),
    (r'\bbios\b|\buefi\b', 'BIOS/UEFI', 3, 'firmware'),
    (r'\byocto\b|\bbuildroot\b', 'Yocto/Buildroot', 3, 'embedded'),
    (r'\bcan bus\b|\bcanopen\b|\bautomotive ethernet\b', 'CAN/automotive networking', 3, 'embedded'),
    (r'\bbacnet\b|\bmodbus\b', 'BACnet/Modbus', 3, 'embedded'),
    (r'\bspi\b|\bi2c\b|\bi²c\b|\buart\b|\brs-?485\b', 'SPI/I2C/UART', 3, 'embedded'),
    (r'\bautosar\b', 'AUTOSAR', 3, 'embedded'),
    (r'\brisc[- ]?v\b', 'RISC-V', 3, 'embedded'),
    (r'\bmips\b|\bpowerpc\b|\bppc\b', 'MIPS/PowerPC', 3, 'embedded'),
    (r'\bxtensa\b', 'Xtensa', 3, 'embedded'),
    (r'\bhypervisor\b', 'hypervisor', 2, 'virtualization'),
    (r'\bkvm\b', 'KVM', 2, 'virtualization'),
    (r'\bvirtuali[sz]ation\b', 'virtualization', 2, 'virtualization'),
    (r'\bdevice drivers?\b|\bkernel drivers?\b', 'device drivers', 2, 'kernel'),
    (r'\bembedded linux\b', 'Embedded Linux', 2, 'embedded'),
    (r'\blinux kernel\b|\bkernel space\b|\bkernel-space\b', 'Linux kernel', 2, 'kernel'),
    (r'\bbare[- ]metal\b', 'bare metal', 2, 'embedded'),
    (r'\bsystems programming\b|\bsystems software\b', 'systems programming', 2, 'kernel'),
    (r'\bmemory management\b|\bvirtual memory\b', 'memory management', 2, 'kernel'),
    (r'\bfpga\b', 'FPGA', 2, 'embedded'),
    (r'\brtos\b|\breal[- ]time operating system\b', 'RTOS', 2, 'embedded'),
    (r'\barm64\b|\baarch64\b|\bcortex[- ]?[mar]\d*\b', 'ARM/Cortex', 2, 'embedded'),
    (r'\bx86(?:-64)?\b|\bx64\b|\b8086\b', 'x86/x64', 2, 'firmware'),
    (r'\bmicrocontrollers?\b|\bmcu\b', 'microcontrollers', 2, 'embedded'),
    (r'\btechnical writ(?:er|ing)\b|\btechnical documentation\b|\btechnical author\b', 'technical writing', 2, 'writing'),
    (r'\bapi documentation\b|\bdeveloper documentation\b|\bdocs-as-code\b', 'developer/API docs', 2, 'writing'),
    (r'\bdita\b|\bsphinx\b|\bmkdocs\b', 'DITA/Sphinx/MkDocs', 3, 'writing'),
    (r'\bdeveloper relations\b|\bdeveloper advocate\b|\bdevrel\b', 'developer relations', 2, 'devrel'),
    (r'\bdeveloper education\b|\btechnical trainer\b|\btechnical instructor\b', 'developer education', 2, 'writing'),
    (r'\bcobol\b', 'COBOL', 2, 'legacy'),
    (r'\bms-?dos\b|\bdosbox(?:-x)?\b|\breal mode\b', 'DOS/real mode', 3, 'legacy'),
    (r'\blegacy systems?\b|\bobsolete systems?\b|\blegacy software\b', 'legacy systems', 2, 'legacy'),
    (r'\bretro comput(?:ing|er)\b|\bvintage comput(?:ing|er)\b', 'retro computing', 3, 'legacy'),
    (r'\bmbedtls\b|\bwolfssl\b|\bopenssl\b|\bx\.509\b', 'TLS/X.509', 3, 'security'),
    (r'\bopenbmc\b', 'OpenBMC', 3, 'firmware'),
    (r'\btrustzone\b|\btrusted execution environment\b|\btee\b', 'TrustZone/TEE', 3, 'security'),
    (r'\bdevice tree\b|\bdts\b|\bdtbo\b', 'Device Tree', 3, 'embedded'),
    (r'\bbsp\b|\bboard support package\b', 'BSP', 3, 'embedded'),
    (r'\bnvme\b|\bssd firmware\b|\bnand\b', 'NVMe/SSD/NAND', 3, 'firmware'),
    (r'\biommu\b|\bvfio\b|\bsr-?iov\b', 'IOMMU/VFIO/SR-IOV', 3, 'virtualization'),
    (r'\bxen\b|\bvmware\b|\bvirtualbox\b', 'Xen/VMware', 3, 'virtualization'),
    (r'\bebpf\b|\bbpf\b', 'eBPF', 3, 'kernel'),
    (r'\blivepatch\b|\blive patching\b|\bkernelcare\b', 'kernel live patching', 3, 'kernel'),
    (r'\belf\b|\bpe/coff\b|\bportable executable\b', 'ELF/PE-COFF', 3, 'reverse'),
    (r'\bdisassembl(?:y|er)\b|\bdecompil(?:e|er|ation)\b', 'disassembly/decompilation', 3, 'reverse'),
    (r'\bvxworks\b|\bthreadx\b|\bazure rtos\b', 'VxWorks/ThreadX', 3, 'embedded'),
    (r'\bfirmware\b', 'firmware', 1, 'firmware'),
    (r'\bembedded systems?\b|\bembedded software\b|\bembedded engineer\b', 'embedded systems', 1, 'embedded'),
    (r'\barm\b', 'ARM', 1, 'embedded'),
    (r'\bc\s*/\s*c\+\+|\bc\+\+\b', 'C/C++', 1, 'kernel'),
    (r'\brust\b', 'Rust', 1, 'kernel'),
    (r'\bassembly\b|\bassembler\b', 'assembly', 1, 'reverse'),
]

_BROAD_PROFILE_TERMS = {'firmware', 'embedded systems', 'arm', 'c/c++', 'python tooling', 'network protocols'}
_CATEGORY_INTEREST = {
    'embedded': 'embedded', 'embedded-niche': 'embedded', 'systems': 'kernel',
    'reverse': 'reverse', 'virtualization': 'virtualization', 'retro': 'legacy',
    'retro-niche': 'legacy', 'writing': 'writing', 'security': 'security',
    'protocol-niche': 'embedded', 'tooling': 'kernel', 'cv-specific': 'kernel',
}

# Broader but still role/JD-grounded terms used only when the specialist cue set has no
# match. These prevent an empty list Summary while making weak/adjacent fit explicit
# rather than inventing niche relevance.
_ADJACENT_PATTERNS = [
    (r'\b(?:generative ai|genai|large language models?|llms?|artificial intelligence|machine learning)\b', 'AI/LLM systems'),
    (r'\bforward[- ]deployed\b|\bcustomer[- ]facing engineering\b|\bclient[- ]facing engineering\b', 'client-facing deployment'),
    (r'\bapi integrations?\b|\bsystems? integrations?\b|\bintegration engineering\b', 'systems integration'),
    (r'\bjava\b|\bspring boot\b', 'Java/backend'),
    (r'\bdevops\b|\bci/cd\b|\bterraform\b|\bansible\b', 'DevOps/automation'),
    (r'\bkubernetes\b|\bdocker\b|\bcontainers?\b', 'containers/Kubernetes'),
    (r'\baws\b|\bazure\b|\bgcp\b|\bcloud infrastructure\b', 'cloud infrastructure'),
    (r'\bgo(?:lang)?\b', 'Go'),
    (r'\bpython\b', 'Python'),
    (r'\bc#\b|\b\.net\b', '.NET/C#'),
    (r'\bbackend\b|\bserver[- ]side\b', 'backend services'),
    (r'\bproduct configuration\b|\bconfiguration engineer\b', 'product configuration'),
    (r'\bengineering manager\b|\btechnical manager\b', 'engineering leadership'),
    (r'\btechnical support\b|\bsupport engineer\b', 'technical support'),
    (r'\bdatabase\b|\bsql\b|\bmysql\b|\bpostgres(?:ql)?\b', 'database/SQL'),
    (r'\blinux\b', 'Linux'),
    (r'\bnetwork(?:ing)?\b|\btcp/ip\b', 'networking'),
]


def normalize_highlight(value, max_words=18):
    """Normalize a compact candidate-interest cue for list display."""
    text=' '.join(str(value or '').replace('\n',' ').split()).strip(' \t\r\n-–—|:;,')
    if not text:
        return ''
    text=re.sub(r'(?i)https?://\S+', '', text).strip()
    low=text.casefold()
    if low in {
        'worth a closer look','worth a closer look.','contract role','contract role.',
        'remote role','remote role.','fully remote role','fully remote role.',
        'remote reverse engineering work','remote reverse engineering work.',
    }:
        return ''
    if re.match(r'(?i)^interesting for its\s+(?:firmware|c/c\+\+|c\+\+|embedded|software|technical)\s+work\.?$',text):
        return ''
    if low.startswith(_GENERIC_PREFIXES) and len(text.split())>12:
        return ''
    words=text.split()
    if len(words)>max_words:
        text=' '.join(words[:max_words]).rstrip(' ,;:-')+'…'
    if len(text)>220:
        text=text[:220].rsplit(' ',1)[0].rstrip(' ,;:-')+'…'
    return text.strip()


def normalize_ai_fit_summary(value, max_words=50):
    """Keep an AI-written Opportunity list cue compact without re-synthesizing it."""
    text=' '.join(str(value or '').replace('\n',' ').split()).strip(' \t\r\n-–—|:;,')
    if not text:
        return ''
    text=re.sub(r'(?i)^(?:highlight|summary|why it fits|fit summary)\s*[:\-–—]+\s*','',text).strip()
    # Em/en dashes became repetitive in list summaries. Keep normal hyphens inside
    # technical terms, but normalize sentence separators to punctuation that reads more
    # naturally in a narrow table cell.
    text=re.sub(r'\s+[—–]\s+', '; ', text)
    # Do not turn a source URL into the list summary. The role/source URL is already shown
    # elsewhere in the list and digest.
    text=re.sub(r'(?i)https?://\S+','',text).strip()
    words=text.split()
    if len(words)>max_words:
        text=' '.join(words[:max_words]).rstrip(' ,;:-')+'…'
    if len(text)>600:
        text=text[:600].rsplit(' ',1)[0].rstrip(' ,;:-')+'…'
    return text



_COMPANY_BOILERPLATE_PATTERNS=(
    r'\bis (?:a|an|the) (?:leading|global|world[- ]leading|privately held|public) (?:provider|company|business|organization|organisation|platform)\b',
    r'\b(?:our|the) (?:company|platform|business|organization|organisation) (?:is|has|provides|serves|powers)\b',
    r'\b(?:widely used|customers around the world|global enterprise|technology markets|market leader|industry leader)\b',
    r'\b(?:founded in|headquartered in|we are a leading|we are the leading)\b',
)

def _looks_like_company_boilerplate(value):
    text=' '.join(str(value or '').split())
    if not text:
        return False
    low=text.casefold()
    hits=sum(1 for pat in _COMPANY_BOILERPLATE_PATTERNS if re.search(pat,low,re.I))
    role_signals=len(_matching_signals(text)) if '_matching_signals' in globals() else 0
    # A strong role-specific technical sentence can mention the company; only reject
    # prose that is dominated by corporate/about-us language.
    return hits>=2 or (hits>=1 and role_signals==0 and len(text.split())>=14)

_GENERIC_FIT_PHRASES = (
    'highly relevant', 'relevant and actionable', 'strong match', 'clear opportunity',
    'aligns with the candidate', "candidate's profile", 'candidate profile',
    'high priority interest', 'high-priority interest', 'worth pursuing',
    'job posting provides', 'job posting is', 'role is a strong',
)


def _generic_ai_fit_text(value):
    """Detect recommendation prose that says *that* a role fits without saying *why*."""
    low=' '.join(str(value or '').split()).casefold()
    if not low:
        return True
    return any(phrase in low for phrase in _GENERIC_FIT_PHRASES)


def ai_result_fit_summary(result):
    """Return a concise, concrete AI-authored technical Opportunity summary."""
    row=result if isinstance(result,dict) else {}
    for key in ('highlight','role_feedback'):
        raw=row.get(key)
        text=normalize_ai_fit_summary(raw,max_words=50)
        if text and not _generic_ai_fit_text(text) and not _looks_like_company_boilerplate(text):
            return text
    return ''


def _templated_or_terse_opportunity_summary(value):
    text=' '.join(str(value or '').split()).strip()
    if len(text.split()) < 18:
        return True
    low=text.casefold()
    return bool(re.search(r'(?i)^(?:technical focus\s*:|[^:]{1,80}:\s*(?:hardware interfaces?|firmware|embedded|board bring[- ]up|rtos|linux|c\+\+|systems?)(?:[ .,+/&-]|$))',text) or
                re.search(r'(?i)\b(?:embedded firmware and platform work|focused embedded work|systems-level engineering work|technical fit)\b',low))

def opportunity_specific_highlight(opportunity=None, *, result=None, title='', description='', facts=None, remote_text=''):
    """Return a JD-grounded technical list summary, capped at 50 words.

    A useful AI/stored sentence is preferred. Deterministic evidence synthesis is used
    for terse legacy cues and records that pre-date the richer summary contract.
    """
    ai=ai_result_fit_summary(result or {})
    if ai:
        return ai
    stored=''
    if opportunity is not None:
        stored=concise_technical_summary(getattr(opportunity,'list_highlight',''))
        # 0.10.37 deliberately generated 2-6 word cues. Keep richer historical summaries,
        # but rebuild terse cues from retained JD evidence when possible.
        if (stored and not _templated_or_terse_opportunity_summary(stored)
                and not _generic_ai_fit_text(stored) and not _looks_like_company_boilerplate(stored)):
            return stored
    derived=derive_opportunity_highlight(
        opportunity,
        result=result,
        title=title,
        description=description,
        facts=facts,
        remote_text=remote_text,
    )
    if derived:
        return normalize_ai_fit_summary(derived,max_words=50)
    return stored

def _fallback_evidence_sentence(text, title=''):
    """Return a readable technical JD sentence when taxonomy matching is sparse.

    Older code fell back to a two-to-six-word keyword tag. That made the Opportunity
    Summary column much less useful than Leads/Address Book. Prefer a compact sentence
    from retained role evidence and keep the same 50-word hard ceiling used by AI output.
    """
    clean=' '.join(str(text or '').replace('\n',' ').split())
    if not clean:
        return ''
    role_terms=[x.casefold() for x in re.findall(r'[A-Za-z][A-Za-z0-9+#./-]{2,}',str(title or '')) if len(x)>2]
    boilerplate=('equal opportunity','privacy policy','cookie policy','terms of use','sign in','apply now','about the company','company overview','leading provider','global enterprise','technology markets','widely used')
    best=None
    for idx,sentence in enumerate(re.split(r'(?<=[.!?])\s+|\s*[•·]\s*',clean)[:500]):
        sentence=' '.join(sentence.split()).strip(' -–—|:;,')
        words=sentence.split()
        low=sentence.casefold()
        if not 9 <= len(words) <= 70 or any(x in low for x in boilerplate) or 'http://' in low or 'https://' in low:
            continue
        technical=len(_matching_signals(sentence))
        title_hits=sum(1 for term in role_terms[:12] if _term_present(sentence,term))
        # A sentence must have at least one concrete role/technical anchor.
        if not technical and not title_hits:
            continue
        score=(technical*18)+(title_hits*4)-abs(min(len(words),50)-25)-(idx*0.02)
        if best is None or score>best[0]:
            best=(score,sentence)
    return normalize_ai_fit_summary(best[1],max_words=50) if best else ''


def _adjacent_cue(title, evidence):
    """Last-resort technical summary without generic fit/recommendation prose."""
    blob=' '.join(str(x or '') for x in (title,evidence))
    found=[]
    for pattern,label in _ADJACENT_PATTERNS:
        if re.search(pattern,blob,re.I) and label not in found:
            found.append(label)
        if len(found)>=3:
            break
    natural=_best_technical_evidence_sentence(evidence,found) if found else ''
    if natural:
        return natural
    if found:
        body=', '.join(found[:-1])+(' and '+found[-1] if len(found)>1 else found[0])
        return normalize_ai_fit_summary(f'The role involves {body}, based on the retained job-page evidence.',max_words=50)
    role=' '.join(str(title or '').split()).strip(' -–—|:;,')
    if role and role.casefold() not in {'untitled opportunity','opportunity'}:
        fallback=_fallback_evidence_sentence(evidence,role)
        if fallback:
            return fallback
        return normalize_ai_fit_summary(role,max_words=50)
    return ''

def _matching_signals(text):
    low=' '.join(str(text or '').split()).casefold()
    found=[]
    seen=set()
    for order,(pattern,label,level,interest) in enumerate(_SIGNAL_PATTERNS):
        if re.search(pattern,low,re.I) and label.casefold() not in seen:
            seen.add(label.casefold())
            found.append({'label':label,'level':level,'interest':interest,'order':order})
    return found


def _specific_enough(signals):
    if not signals:
        return False
    levels=[x['level'] for x in signals]
    # One substantive target-domain signal is useful enough. Broad terms such as
    # firmware/ARM/C++ still need a second supporting signal.
    return any(x>=2 for x in levels) or sum(1 for x in levels if x==1)>=2


def _explicit_is_specific(text):
    return _specific_enough(_matching_signals(text))


def is_specific_highlight(value):
    text=normalize_highlight(value)
    return bool(text and _explicit_is_specific(text))


def _term_present(text, term):
    clean=' '.join(str(term or '').split()).strip().casefold()
    if not clean:
        return False
    blob=' '.join(str(text or '').split()).casefold()
    if re.fullmatch(r'[a-z0-9 +#./-]+',clean):
        return bool(re.search(r'(?<![a-z0-9])'+re.escape(clean)+r'(?![a-z0-9])',blob,re.I))
    return clean in blob


def _grounded_profile_signals(facts, trusted):
    """Reuse saved CV/profile matches only when the actual JD contains them.

    Search snippets can echo query wording, so saved discovery matches are never trusted
    by themselves. This path validates each candidate concept against fetched/stored JD
    evidence, then turns it into one more short list keyword when useful.
    """
    if not isinstance(facts,dict) or not trusted:
        return []
    candidates=[]
    for key in ('cv_profile_matches','rediscovered_profile_matches'):
        value=facts.get(key) or []
        if isinstance(value,(list,tuple,set)):
            candidates.extend(str(x).strip() for x in value if str(x).strip())
    if not candidates:
        return []
    try:
        from .queryplanner import SKILL_GRAPH
    except Exception:
        SKILL_GRAPH={}
    out=[]; seen=set()
    for idx,canonical in enumerate(candidates):
        spec=SKILL_GRAPH.get(canonical) or {}
        variants=[canonical]+list(spec.get('patterns') or [])+list(spec.get('aliases') or [])
        if not any(_term_present(trusted,v) for v in variants if v):
            continue
        label=canonical
        if label.casefold() in seen:
            continue
        seen.add(label.casefold())
        category=str(spec.get('category') or '')
        interest=_CATEGORY_INTEREST.get(category,'kernel')
        score=float(spec.get('weight') or 0)
        level=1 if canonical.casefold() in _BROAD_PROFILE_TERMS else (3 if score>=10 else 2)
        out.append({'label':label,'level':level,'interest':interest,'order':1000+idx})
    return out


def _merge_signals(*groups):
    out=[]; seen=set()
    for group in groups:
        for item in group or []:
            key=item['label'].casefold()
            if key in seen:
                continue
            seen.add(key); out.append(item)
    return out



def _ranked_signal_labels(signals, limit=5):
    if not _specific_enough(signals):
        return []
    ranked=sorted(signals,key=lambda x:(-x['level'],x['order']))
    chosen=[]
    for item in ranked:
        low=item['label'].casefold()
        if any(low in old.casefold() or old.casefold() in low for old in chosen):
            continue
        chosen.append(item['label'])
        if len(chosen)>=limit:
            break
    return chosen


def _best_technical_evidence_sentence(text, labels):
    """Pick one readable JD sentence containing the strongest technical evidence."""
    clean=' '.join(str(text or '').replace('\n',' ').split())
    if not clean or not labels:
        return ''
    candidates=re.split(r'(?<=[.!?])\s+|\s*[•·]\s*',clean)
    best=None
    for idx,sentence in enumerate(candidates[:500]):
        sentence=' '.join(sentence.split()).strip(' -–—|:;,')
        words=sentence.split()
        if not 7 <= len(words) <= 60 or 'http://' in sentence.casefold() or 'https://' in sentence.casefold():
            continue
        hits=sum(1 for label in labels if _term_present(sentence,label))
        if not hits:
            continue
        generic=sum(1 for phrase in _GENERIC_FIT_PHRASES if phrase in sentence.casefold())
        score=(hits*20) - abs(min(len(words),50)-24) - generic*30 - idx*0.01
        if best is None or score>best[0]:
            best=(score,sentence)
    return normalize_ai_fit_summary(best[1],max_words=50) if best else ''


def _summary_from_signals(signals, title, evidence):
    labels=_ranked_signal_labels(signals,limit=5)
    if not labels:
        return ''
    natural=_best_technical_evidence_sentence(evidence,labels)
    if natural:
        return natural
    # Evidence can be highly structured with no usable sentence (JSON/schema/list data).
    # In that case present the concrete technical concepts without generic fit language.
    if len(labels)==1:
        body=labels[0]
    elif len(labels)==2:
        body=f'{labels[0]} and {labels[1]}'
    else:
        body=', '.join(labels[:-1])+f', and {labels[-1]}'
    return normalize_ai_fit_summary(f'The role involves {body}, based on the retained job-page evidence.',max_words=50)


def derive_opportunity_highlight(opportunity=None, *, result=None, title='', description='', facts=None, remote_text=''):
    """Return a concise JD-grounded technical Opportunity summary (maximum 50 words).

    Fetched/stored JD evidence is authoritative. Search-query wording is excluded unless
    the role title itself establishes the same target domain. Historical records can be
    rebuilt from retained ``ai_job_summary.source_text`` when visible description is blank.
    """
    result=result or {}
    raw_snippet=''
    if opportunity is not None:
        title=title or getattr(opportunity,'title','')
        description=description or getattr(opportunity,'description','')
        facts=facts if facts is not None else (getattr(opportunity,'extracted_facts',{}) or {})
        raw_snippet=getattr(opportunity,'raw_search_snippet','') or ''
    facts=facts or {}

    evidence_parts=[title, description]
    for key in ('summary','evidence'):
        value=result.get(key)
        if value:
            evidence_parts.append(value)
    if isinstance(facts,dict):
        ai=facts.get('ai_job_summary') if isinstance(facts.get('ai_job_summary'),dict) else {}
        cloud=facts.get('cloud_research') if isinstance(facts.get('cloud_research'),dict) else {}
        role_info=facts.get('role_info') if isinstance(facts.get('role_info'),dict) else {}
        hiring=facts.get('hiring_process') if isinstance(facts.get('hiring_process'),dict) else {}
        for value in (ai.get('source_text'), ai.get('text'), cloud.get('summary'), role_info.get('summary'), hiring.get('summary')):
            if value:
                evidence_parts.append(value)

    trusted=' '.join(str(x or '') for x in evidence_parts)[:48000]
    signals=_merge_signals(_matching_signals(trusted),_grounded_profile_signals(facts,trusted))

    title_signals=_matching_signals(title)
    if not _specific_enough(signals) and title_signals and raw_snippet:
        signals=_merge_signals(signals,_matching_signals(' '.join([title,raw_snippet])))

    # Prefer a natural retained-JD sentence over the old taxonomy-shaped cue. This gives
    # the list similar substance to Hidden Leads while remaining grounded and <=50 words.
    labels=_ranked_signal_labels(signals,limit=5)
    natural=_best_technical_evidence_sentence(trusted,labels) or _fallback_evidence_sentence(trusted,title)
    if natural:
        return natural
    summary=_summary_from_signals(signals,title,trusted)
    if summary:
        return summary
    adjacent=_adjacent_cue(title,trusted)
    return normalize_ai_fit_summary(adjacent,max_words=50) if adjacent else ''


def concise_technical_summary(value):
    """Normalize historical Opportunity summaries without reducing them to keyword tags."""
    text=' '.join(str(value or '').replace('\n',' ').split()).strip(' -–—|:;,')
    if not text:
        return ''
    text=re.sub(r'(?i)^(?:summary|highlight|why it fits|fit summary)\s*[:\-–—]+\s*','',text).strip()
    # Fix the 0.10.36/0.10.37 repeated form: ``X: X-focused ...``. When only that
    # regression remains, retain X as a safe fallback; the retrospective backfill will
    # rebuild it from retained JD evidence when available.
    m=re.match(r'(?i)^([^:]{2,100})\s*:\s*\1[- ]focused\b.*$',text)
    if m:
        text=m.group(1).strip()
    text=re.sub(r'(?i)https?://\S+','',text).strip()
    return normalize_ai_fit_summary(text,max_words=50)
