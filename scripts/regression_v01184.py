from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from portal.services.query_normalizer import _normalize_site_scope


read = lambda name: (root / name).read_text(encoding="utf-8")

assert read("VERSION").strip() == "0.11.84"
assert read("RELEASE_ID").strip() == "ScoutBox 0.11.84"
assert read("BUILD_INFO.txt").strip() == "ScoutBox v0.11.84"
assert read("README.md").splitlines()[0] == "# ScoutBox 0.11.84"
assert (root / "docs/RELEASE_NOTES_0.11.84.md").exists()

telemetry = read("templates/portal/telemetry.html")
css = read("portal/static/portal/app.css")
email = read("templates/portal/email_config.html")

assert "title.textContent='Discovery Activity'" in telemetry
assert "Discovery Performance Details" not in telemetry
assert 'id="token-ring-summary"' in telemetry
assert 'id="discovery-ring-summary"' in telemetry
assert 'id="market-language-total"' in telemetry
assert 'id="market-country-total"' in telemetry
assert "function updateTelemetrySummaries()" in telemetry
assert "tokens_in||0" in telemetry and "reasoning_tokens||0" in telemetry
assert "providerData.reduce((sum,row)=>sum+Number(row.requests||0),0)" in telemetry
assert "marketCoverageData.languages||[]" in telemetry
assert ".telemetry-ring-summary .ring-total" in css
assert ".market-coverage-heading-total" in css

assert 'style="padding-top:14px" id="imap-browser"' in email
assert 'border-top:1px solid var(--line);padding-top:14px' not in email
assert '#provider-config-form .provider-config-row{border-bottom:0!important}' in css
assert email.count('class="outgoing-subheading"') == 3
assert 'class="top-gap outgoing-test-section" style="padding-top:14px"' in email
assert '.outgoing-subheading{margin:12px 0 8px!important;padding:0!important;border:0!important;text-align:left}' in css

# Provider compatibility is intentional: bare country/registry scopes are valid for
# providers that implement country-wide site searches.
assert _normalize_site_scope("site:.kr") == "site:.kr"
assert _normalize_site_scope("site:.com.kr") == "site:.com.kr"
assert "valid_site_scope_host" not in read("portal/services/query_normalizer.py")
assert "valid_site_scope_host" not in read("portal/services/queryplanner.py")

print("ScoutBox 0.11.84 regression checks passed")
