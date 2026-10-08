from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
for rel in ["cold_contact.html", "opportunities.html", "contacts.html"]:
    text = (ROOT / "templates" / "portal" / rel).read_text()
    assert "manualFilterHasMeaningfulResult" in text, rel
    assert "processed||0)>0||Number(d.result?.kept" not in text, rel
    assert "sessionStorage.setItem" in text, rel
print("0.11.23 regression ok")
