from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('portal', '0008_v086_ui_read_summary')]
    operations = [
        migrations.CreateModel(
            name='TrackingSuffixReserve',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('suffixes', models.JSONField(blank=True, default=list)),
                ('cursor', models.PositiveIntegerField(default=0)),
                ('generated_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('rule', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='suffix_reserve', to='portal.trackinglinkrule')),
            ],
        ),
    ]
