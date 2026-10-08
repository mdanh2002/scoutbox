from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('portal', '0150_v01153_hidden_lead_summary_marker_cleanup')]

    operations = [
        migrations.AddField(
            model_name='portalsettings', name='opportunity_selectivity',
            field=models.CharField(choices=[('broad','Broad'),('balanced','Balanced'),('specialist','Specialist')], default='balanced', help_text='Admission breadth for automatically discovered Opportunities.', max_length=16),
        ),
        migrations.AddField(
            model_name='portalsettings', name='lead_selectivity',
            field=models.CharField(choices=[('broad','Broad'),('balanced','Balanced'),('specialist','Specialist')], default='balanced', help_text='Admission breadth for automatically discovered Hidden Leads.', max_length=16),
        ),
        migrations.AddField(
            model_name='portalsettings', name='contact_selectivity',
            field=models.CharField(choices=[('broad','Broad'),('balanced','Balanced'),('verified','Verified')], default='balanced', help_text='Identity/admission strictness for automatically discovered Address Book contacts.', max_length=16),
        ),
    ]
