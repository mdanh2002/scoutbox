from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[('portal','0092_v01041_role_location')]
    operations=[
        migrations.AddField(model_name='opportunity',name='target_response_bytes',field=models.PositiveBigIntegerField(default=0,help_text='Latest useful successful response size for URL-health tooltip display.')),
        migrations.AddField(model_name='companylead',name='target_response_bytes',field=models.PositiveBigIntegerField(default=0,help_text='Latest useful successful response size for URL-health tooltip display.')),
        migrations.AddField(model_name='contact',name='domain_response_bytes',field=models.PositiveBigIntegerField(default=0,help_text='Latest useful successful response size for URL-health tooltip display.')),
    ]
