#!/usr/bin/env python3
"""Static regressions for ScoutBox 0.11.52 Hidden Lead summary evidence markers."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
def read(rel): return (ROOT/rel).read_text(encoding='utf-8')

def section(text,start,end=None):
    i=text.index(start)
    if end is None: return text[i:]
    j=text.index(end,i+len(start))
    return text[i:j]

assert read('VERSION').strip()=='0.11.52'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.52'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.52'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.52'
assert (ROOT/'docs'/'RELEASE_NOTES_0.11.52.md').exists()

cold=read('portal/services/cold.py')
assert 'def hidden_lead_summary_has_evidence_markers(summary):' in cold
assert '_HIDDEN_LEAD_EVIDENCE_SECTION_RE=re.compile(' in cold
for marker in ('PAGE_TITLE','QUALIFICATIONS','APPLICATION','COMPANY_PROFILE','SOURCE_URL','TEXT'):
    assert marker in cold, f'missing structured evidence marker {marker}'
assert '_HIDDEN_LEAD_EVIDENCE_PREFIX_RE' in cold, 'generic leading bracket-marker guard missing'

candidate=section(cold,"def _specific_company_summary_candidate(summary, company=''):","\n\ndef market_summary_needs_refresh")
assert 'hidden_lead_summary_has_evidence_markers(summary)' in candidate, 'summary candidate does not reject evidence labels'
refresh=section(cold,'def market_summary_needs_refresh(summary):','\n\ndef _organization_context')
assert 'hidden_lead_summary_has_evidence_markers(text)' in refresh, 'stored marker summary is not refreshable'

fallback=section(cold,'def _evidence_summary_fallback(company,title,text,max_words=58):','\n\ndef _named_offerings')
assert '_company_summary_evidence_segments(text)' in fallback, 'fallback ignores structured section boundaries'
assert "section=='PAGE_TITLE'" in fallback, 'PAGE_TITLE article/tutorial guard missing'
segments=section(cold,'def _company_summary_evidence_segments(text):','\n\ndef hidden_lead_summary_is_generic')
assert '_HIDDEN_LEAD_SUMMARY_SKIP_SECTIONS' in segments
for marker in ('APPLICATION','QUALIFICATIONS','FOOTER','NAVIGATION'):
    assert marker in cold[cold.index('_HIDDEN_LEAD_SUMMARY_SKIP_SECTIONS'):cold.index('def hidden_lead_summary_has_evidence_markers')]

extras=read('portal/templatetags/portal_extras.py')
assert 'hidden_lead_summary_has_evidence_markers' in extras.splitlines()[7], 'template helper import missing'
noise=section(extras,'def _hidden_lead_summary_noise(value):','\n\ndef _sentence_start')
assert 'hidden_lead_summary_has_evidence_markers(raw)' in noise, 'display noise guard does not catch section labels'
summary=section(extras,'def hidden_lead_list_summary(lead):','\n\ndef _discovery_origin')
assert "evidence=getattr(lead,'evidence','')" not in summary, 'Hidden Lead list still renders raw evidence as a summary fallback'
assert "return 'Summary pending.'" in summary
assert 'not hidden_lead_summary_has_evidence_markers(retained)' in summary

# The user's observed extraction labels must be covered by the concrete marker contract.
pattern=re.compile(r'\[(PAGE_TITLE|CURRENT_JOB_HEADER|JOB_DESCRIPTION|RESPONSIBILITIES|QUALIFICATIONS|BENEFITS|COMPENSATION|APPLICATION|COMPANY_PROFILE|RELATED_JOBS|FOOTER|NAVIGATION|SOURCE_URL|TITLE|TEXT)\]',re.I)
sample='[APPLICATION] Software Defined Radios. [QUALIFICATIONS] RF sampling. [PAGE_TITLE] Firmware maintenance.'
assert len(pattern.findall(sample))==3

print('ScoutBox 0.11.52 regression checks passed')
