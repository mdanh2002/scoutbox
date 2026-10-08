from django.db import migrations, models


def seed_digest_recipient(apps, schema_editor):
    PortalSettings=apps.get_model('portal','PortalSettings')
    User=apps.get_model('auth','User')
    row=PortalSettings.objects.filter(pk=1).first()
    if not row or str(getattr(row,'digest_recipient_email','') or '').strip():
        return
    email=(User.objects.filter(is_active=True,is_staff=True).exclude(email='').order_by('pk').values_list('email',flat=True).first() or '').strip()
    if email:
        row.digest_recipient_email=email
        row.save(update_fields=['digest_recipient_email'])


class Migration(migrations.Migration):
    dependencies=[('portal','0059_v08101_outgoing_resend_summary')]
    operations=[
        migrations.AddField(
            model_name='portalsettings',
            name='digest_recipient_email',
            field=models.EmailField(blank=True,default='',help_text='Recipient for scheduled and test 24-hour digest email.',max_length=254),
        ),
        migrations.RunPython(seed_digest_recipient,migrations.RunPython.noop),
    ]
