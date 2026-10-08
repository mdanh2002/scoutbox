from django.db import migrations


def forwards(apps, schema_editor):
    SearchSource=apps.get_model('portal','SearchSource')
    AuditLog=apps.get_model('portal','AuditLog')

    # SearchAPI is one account/credential in the unified UI. Promote a legacy child
    # credential only when the hub has none, then remove child copies so old per-service
    # values can never diverge from the key the user sees and saves.
    hub=SearchSource.objects.filter(name='SearchAPI · Google Jobs').first()
    if hub:
        if not hub.api_key_enc:
            donor=(SearchSource.objects.filter(name__startswith='SearchAPI ·')
                   .exclude(pk=hub.pk).exclude(api_key_enc='').order_by('pk').first())
            if donor:
                hub.api_key_enc=donor.api_key_enc
                hub.save(update_fields=['api_key_enc'])
        SearchSource.objects.filter(name__startswith='SearchAPI ·').exclude(pk=hub.pk).update(api_key_enc='')

    if not AuditLog.objects.filter(action='version_upgraded',version='0.11.138').exists():
        AuditLog.objects.create(
            action='version_upgraded',version='0.11.138',summary='ScoutBox upgraded to version 0.11.138.',
            metadata={
                'release':'0.11.138',
                'searchapi_account_endpoint_validation':True,
                'searchapi_success_auto_confirms_credential':True,
                'searchapi_shared_credential_canonicalization':True,
                'searchapi_extra_param_auth_shadow_fix':True,
            },
        )


class Migration(migrations.Migration):
    dependencies=[('portal','0209_v011137_searchapi_validation_polish')]
    operations=[migrations.RunPython(forwards,migrations.RunPython.noop)]
