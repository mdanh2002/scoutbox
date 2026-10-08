from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies=[('portal','0023_v0826_hidden_leads_blacklist_scope')]
    operations=[
        migrations.AddField(model_name='application',name='generated_cover',field=models.FileField(blank=True,upload_to='generated/%Y/%m/')),
        migrations.AddField(model_name='application',name='generated_cover_pdf',field=models.FileField(blank=True,upload_to='generated/%Y/%m/')),
        migrations.AddField(model_name='application',name='attach_generated_cv',field=models.BooleanField(default=False)),
        migrations.AddField(model_name='application',name='attach_generated_cv_pdf',field=models.BooleanField(default=False)),
        migrations.AddField(model_name='application',name='attach_generated_cover',field=models.BooleanField(default=False)),
        migrations.AddField(model_name='application',name='attach_generated_cover_pdf',field=models.BooleanField(default=False)),
        migrations.AlterField(model_name='sourceblacklist',name='scope',field=models.CharField(choices=[('all','Always'),('opportunities','Opportunities Only'),('hidden_leads','Hidden Leads Only')],default='all',max_length=24)),
    ]
