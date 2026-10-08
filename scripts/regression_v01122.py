from pathlib import Path

base = Path(__file__).resolve().parents[1]
for rel in [
    "templates/portal/contacts.html",
    "templates/portal/cold_contact.html",
    "templates/portal/opportunities.html",
]:
    text = (base / rel).read_text()
    assert "No useful per-entry result details were recorded for this run." in text, rel
    assert "run.status != 'running' and run.status != 'queued'" in text, rel
print("0.11.22 regression OK")
