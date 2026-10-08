#!/usr/bin/env python3
"""Static regressions for ScoutBox 0.11.53 readable Hidden Lead summary fallbacks."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
def read(rel): return (ROOT/rel).read_text(encoding='utf-8')
def section(text,start,end=None):
    i=text.index(start)
    if end is None: return text[i:]
    j=text.index(end,i+len(start))
    return text[i:j]

assert read('VERSION').strip()=='0.11.53'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.53'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.53'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.53'
assert (ROOT/'docs'/'RELEASE_NOTES_0.11.53.md').exists()
assert (ROOT/'portal/migrations/0150_v01153_hidden_lead_summary_marker_cleanup.py').exists()

cold=read('portal/services/cold.py')
assert 'def strip_hidden_lead_evidence_markers(value):' in cold
stripper=section(cold,'def strip_hidden_lead_evidence_markers(value):','\n\ndef _company_summary_evidence_segments')
assert "_HIDDEN_LEAD_EVIDENCE_SECTION_RE.sub(' ',text)" in stripper
assert "_HIDDEN_LEAD_EVIDENCE_PREFIX_RE.sub('',text)" in stripper
candidate=section(cold,"def _specific_company_summary_candidate(summary, company=''):",'\n\ndef market_summary_needs_refresh')
assert 'strip_hidden_lead_evidence_markers(summary)' in candidate
assert "if hidden_lead_summary_has_evidence_markers(summary):\n        return ''" not in candidate

extras=read('portal/templatetags/portal_extras.py')
assert 'strip_hidden_lead_evidence_markers' in extras.splitlines()[7]
usable=section(extras,'def usable_hidden_lead_summary(value):','\n\ndef _useful_opportunity_text')
assert 'strip_hidden_lead_evidence_markers' in usable
summary=section(extras,'def hidden_lead_list_summary(lead):','\n\ndef _discovery_origin')
assert "clean_stored=strip_hidden_lead_evidence_markers(stored)" in summary
assert "evidence=strip_hidden_lead_evidence_markers(getattr(lead,'evidence',''))" in summary
assert "return 'Summary pending.'" not in summary
assert "return ''" in summary
noise=section(extras,'def _hidden_lead_summary_noise(value):','\n\ndef _sentence_start')
assert "'summary pending'" in noise

views=read('portal/views.py')
repair=section(views,'    refreshable=[','    queued_summary_ids=set()')
assert ") or 'Summary pending.'" not in repair
assert 'if repaired and repaired != lead.summary:' in repair

tasks=read('portal/tasks.py')
job=section(tasks,'def market_lead_summary_job','\n\ndef _maintenance_company_info_missing')
assert "fallback or 'Summary pending.'" not in job
assert "lead.summary=''" in job
assert "strip_hidden_lead_evidence_markers(review.get('summary'))" in tasks

discovery=read('portal/services/discovery.py')
assert "strip_hidden_lead_evidence_markers(admission.get('summary'))" in discovery
cloud=read('portal/services/cloud_discovery.py')
assert 'strip_hidden_lead_evidence_markers' in cloud
assert "strip_hidden_lead_evidence_markers(lead_gate.get('summary'))" in cloud

migration=read('portal/migrations/0150_v01153_hidden_lead_summary_marker_cleanup.py')
assert "original.strip().casefold() == 'summary pending.'" in migration
assert "SECTION_RE.sub(' ', original)" in migration
assert "CompanyLead.objects.filter(pk=lead.pk).update(summary=cleaned)" in migration

# Concrete user case: labels disappear while the useful sentence survives verbatim.
pattern=re.compile(r'\[(PAGE_TITLE|CURRENT_JOB_HEADER|JOB_DESCRIPTION|RESPONSIBILITIES|QUALIFICATIONS|BENEFITS|COMPENSATION|APPLICATION|COMPANY_PROFILE|RELATED_JOBS|FOOTER|NAVIGATION|SOURCE_URL|TITLE|TEXT)\]',re.I)
sample='[QUALIFICATIONS] Software defined radio systems often require: Direct radio frequency (RF) sampling to achieve high bandwidth and dynamic range with fast frequency hopping.'
clean=re.sub(r'\s+',' ',pattern.sub(' ',sample)).strip(' \t\r\n-–—|·:;')
assert clean.startswith('Software defined radio systems often require:')
assert '[QUALIFICATIONS]' not in clean

multi='[APPLICATION] Software Defined Radios, Gear & Guides. [PAGE_TITLE] Firmware Updates and Maintenance.'
clean_multi=re.sub(r'\s+',' ',pattern.sub(' ',multi)).strip()
assert clean_multi=='Software Defined Radios, Gear & Guides. Firmware Updates and Maintenance.'

print('ScoutBox 0.11.53 regression checks passed')
