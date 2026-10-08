from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[("portal","0151_v01154_independent_selectivity")]
    operations=[migrations.AlterField(model_name="blogstatsconfig",name="enabled",field=models.BooleanField(default=True))]
