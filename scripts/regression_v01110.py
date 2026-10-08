from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "portal" / "static" / "portal" / "app.css"
text = CSS.read_text()
assert 'select.toolbar-uniform[name="read"]' in text
assert 'min-width: 150px !important' in text
assert '.contact-read-filter' in text
print("0.11.10 read-filter width regression passed")
