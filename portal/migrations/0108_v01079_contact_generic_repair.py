from django.db import migrations


FUNCTIONAL_LOCALPARTS = {
    "jobs", "job", "careers", "career", "recruiting", "recruitment", "recruit",
    "recruiter", "recruiters", "talent", "hr", "askhr", "humanresources", "people",
    "peopleops", "people-ops", "hello", "info", "contact", "contacts", "sales",
    "marketing", "campaign", "campaigns", "communications", "community", "partnerships",
    "businessdevelopment", "business-development", "support", "help", "service",
    "customer", "customerservice", "admin", "office", "team", "work", "billing",
    "enquiries", "inquiries", "noreply", "no-reply", "donotreply", "applications",
    "application", "apply", "hiring",
}


def repair_functional_contact_flags(apps, schema_editor):
    """Mark previously retained functional/shared mailboxes as generic.

    This is classification repair only: no Address Book entry is deleted.
    """
    Contact = apps.get_model("portal", "Contact")
    for contact in Contact.objects.filter(generic=False).only("pk", "email"):
        email = str(contact.email or "").strip().lower()
        local = email.split("@", 1)[0].split("+", 1)[0]
        tokens = [part for part in local.replace(".", "-").replace("_", "-").split("-") if part]
        normalized = "-".join(tokens)
        compact = "".join(ch for ch in local if ch.isalnum())
        generic = (
            any(token in FUNCTIONAL_LOCALPARTS for token in tokens)
            or normalized in FUNCTIONAL_LOCALPARTS
            or any(normalized.startswith(value + "-") for value in FUNCTIONAL_LOCALPARTS)
            or "sales" in compact
            or any(value in compact for value in ("noreply", "donotreply", "mailerdaemon"))
        )
        if generic:
            Contact.objects.filter(pk=contact.pk).update(generic=True)


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0107_v01077_addressbook_audit_cleanup"),
    ]

    operations = [
        migrations.RunPython(repair_functional_contact_flags, migrations.RunPython.noop),
    ]
