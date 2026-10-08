from pathlib import Path


root = Path(__file__).resolve().parents[1]
read = lambda name: (root / name).read_text(encoding="utf-8")

assert read("VERSION").strip() == "0.11.86"
assert read("RELEASE_ID").strip() == "ScoutBox 0.11.86"
assert read("BUILD_INFO.txt").strip() == "ScoutBox v0.11.86"
assert read("README.md").splitlines()[0] == "# ScoutBox 0.11.86"
assert (root / "docs/RELEASE_NOTES_0.11.86.md").exists()

models = read("portal/models.py")
views = read("portal/views.py")
tasks = read("portal/tasks.py")
telemetry = read("templates/portal/telemetry.html")
links = read("templates/portal/links.html")
recycle = read("templates/portal/recycle_bin.html")
base = read("templates/portal/base.html")
ui = read("portal/ui.py")
ai = read("portal/services/ai.py")
blogstats = read("portal/services/blogstats.py")
migration = read("portal/migrations/0158_v01186_audit_facebook_pages.py")

assert "class AuditLog" in models and "version = models.CharField" in models
assert "class FacebookPage" in models and "evidence_text = models.TextField" in models
assert "class TrackingLink" in models and "When this tracking link was moved to the Recycle Bin" in models
assert "scheduler_silence" not in tasks
assert "version_upgraded" in migration and "metadata__web_search=True" in migration

assert "Facebook Pages" in ui and "Tracking Links" in ui
assert "show_deleted=show_deleted" in views
assert "Moved {count} tracking link(s) to the Recycle Bin" in views
assert "item_type=='tracking_link'" in views
assert "filter_type':'tracking_link'" in views
assert "Tracking Link" in recycle
assert "name=\"link_id\"" not in links
assert "show_deleted" in links and "restoreInlineItem('tracking_link'" in links
assert "TrackingLink.objects.filter(deleted_at__isnull=True)" in blogstats

assert ">Downloaded<" in telemetry and ">Disk Usage<" in telemetry
assert "Downloaded MB" not in telemetry and "ScoutBox Disk Used (MB)" not in telemetry
assert "AI Web Searches" in telemetry
assert "No provider reported a separate reasoning-token count" in telemetry
assert "resourceDisplayRange" in telemetry and "resourcePointX" in telemetry
assert "web_queries_count':web_calls" in ai

assert "initSharedDateRangeFilters" in base
assert "©" in read("templates/portal/about.html") and "All rights reserved" in read("templates/portal/about.html")

print("ScoutBox 0.11.86 regression checks passed")
