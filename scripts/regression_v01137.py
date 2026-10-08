#!/usr/bin/env python3
"""Static regression checks for ScoutBox 0.11.37 UI hotfixes."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
stats = (ROOT / 'templates/portal/stats.html').read_text()
css = (ROOT / 'portal/static/portal/app.css').read_text()
opps = (ROOT / 'templates/portal/opportunities.html').read_text()
hidden = (ROOT / 'templates/portal/cold_contact.html').read_text()
recycle = (ROOT / 'templates/portal/recycle_bin.html').read_text()

checks = [
    ("0.11.37 CSS marker present", "ScoutBox 0.11.37" in css),
    ("Zoom stop range includes 25 through 1000", "const zoomStops=[25,50,75,100,125,150,175,200,250,300,400,500,750,1000]" in stats),
    ("Zoom max no longer clamps to 100", "Math.min(100," not in stats and "zoomIn.disabled=zoom>=100" not in stats),
    ("Zoom label can display 1000%", "grid-template-columns:30px 64px 30px!important" in css),
    ("Markers stay fixed-size while map canvas grows", "canvas.style.width=(width*zoom/100)+'px'" in stats and "canvas.style.height=(height*zoom/100)+'px'" in stats and "btn.style.width=size+'px'" in stats and "btn.style.height=size+'px'" in stats),
    ("Marker maximum size is bounded", "max-width:30px!important" in css and "max-height:30px!important" in css),
    ("Opportunity status uses pie chart", "function drawStatus(){drawLegendPie('status-chart'" in stats and "verticalBars('status-chart'" not in stats),
    ("Search provider summary uses pie chart", "function drawProvider()" in stats and "drawLegendPie('provider-chart'" in stats and "verticalBars('provider-chart'" not in stats),
    ("Reusable pie legend helper exists", "function drawLegendPie(id,items,emptyLabel)" in stats),
    ("Opportunity re-evaluate tooltip is brief", 'title="Re-evaluate selected opportunities"' in opps and 'selecting the whole page offers' not in opps),
    ("Hidden Lead re-evaluate tooltip is brief", 'title="Re-evaluate selected Hidden Leads"' in hidden and 'selecting the whole page offers' not in hidden),
    ("Recycle footer controls moved to left", '<div class="recycle-footer-left"><label>Rows <select data-async-page-size-for="recycle-bin"' in recycle),
    ("Recycle footer center no longer holds controls", '<div class="recycle-footer-center"><label>Rows' not in recycle),
    ("Recycle footer left label styling exists", '.recycle-footer-left label{' in css and '.recycle-footer-left label select{' in css),
]
failed = [name for name, ok in checks if not ok]
if failed:
    raise SystemExit('0.11.37 regression failed: ' + ', '.join(failed))
print('0.11.37 regression checks passed')
