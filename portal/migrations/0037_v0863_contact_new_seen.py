from django.db import migrations, models


def mark_existing_contacts_seen(apps, schema_editor):
    Contact = apps.get_model("portal", "Contact")
    Contact.objects.all().update(is_read=True)


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("portal", "0036_v0854_outreach_backing_visibility")]
    operations = [
        migrations.AddField(
            model_name="contact",
            name="is_read",
            field=models.BooleanField(default=False, db_index=True, help_text="Address Book review state. False is shown as New; True is shown as Seen."),
        ),
        migrations.RunPython(mark_existing_contacts_seen, reverse_noop),
    ]
