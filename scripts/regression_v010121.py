#!/usr/bin/env python3
"""ScoutBox 0.10.121 regression checks."""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from bs4 import BeautifulSoup
from portal.services.pagefetch import structured_visible_text, structured_visible_sections

html = '''
<html><body><main>
<h1>Senior Software Engineer</h1>
<section><h2>Role snapshot</h2><div><span>Remote from</span><span>USA</span></div><div><span>Salary</span><span>USD 160k</span></div></section>
<section><h2>Opportunity details</h2><p>Build borrower-facing software.</p><p>Company serves customers worldwide.</p></section>
<section><h2>About the company</h2><p>Offices worldwide.</p></section>
<section><h2>Related remote jobs</h2><p>Remote from LATAM</p></section>
</main></body></html>
'''
text = structured_visible_text(BeautifulSoup(html, 'html.parser'))
assert '[CURRENT_JOB_HEADER]' in text
assert 'Remote from: USA' in text
assert 'Remote from | USA' not in text
assert 'Salary: USD 160k' in text
assert 'Remote from LATAM' not in text
assert '[RELATED_JOBS]' in text
sections = structured_visible_sections(BeautifulSoup(html, 'html.parser'))
assert 'CURRENT_JOB_HEADER' in sections
assert 'Remote from: USA' in sections['CURRENT_JOB_HEADER']
assert 'LATAM' not in sections.get('CURRENT_JOB_HEADER','')
print('ScoutBox 0.10.121 regressions passed')
