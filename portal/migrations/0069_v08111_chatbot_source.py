from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies=[('portal','0068_v08108_usage_visibility_salary_cleanup')]
    operations=[
        migrations.AddField(
            model_name='chatbotmessage',
            name='source_provider',
            field=models.CharField(blank=True,max_length=40),
        ),
        migrations.AddField(
            model_name='chatbotmessage',
            name='source_model',
            field=models.CharField(blank=True,max_length=300),
        ),
    ]
