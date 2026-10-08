"""Persistence-level blacklist invariant for employer identity changes."""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Opportunity, CompanyLead, Application
from .services.blacklist import matching_blacklist_for_record


def _block_opportunity(instance):
    if not instance.pk or instance.user_deleted or instance.suppressed:
        return
    blocked,_=matching_blacklist_for_record(instance,'opportunities')
    if not blocked:
        return
    now=timezone.now(); label=(blocked.domain or blocked.label or 'company-name rule')
    changed=Opportunity.objects.filter(pk=instance.pk,user_deleted=False,suppressed=False).update(
        suppressed=True,user_deleted=True,deleted_at=now,is_read=True,
        rejection_reason=f'Blocked by blacklist: {label}'[:2000],updated_at=now,
    )
    if changed:
        Application.objects.filter(opportunity_id=instance.pk,deleted_at__isnull=True).update(deleted_at=now,is_read=True)


def _block_lead(instance):
    if not instance.pk or instance.user_deleted:
        return
    blocked,_=matching_blacklist_for_record(instance,'hidden_leads')
    if not blocked:
        return
    now=timezone.now()
    CompanyLead.objects.filter(pk=instance.pk,user_deleted=False).update(user_deleted=True,deleted_at=now,is_read=True,updated_at=now)


@receiver(post_save,sender=Opportunity,dispatch_uid='scoutbox-blacklist-opportunity-invariant')
def opportunity_blacklist_invariant(sender,instance,**kwargs):
    try: _block_opportunity(instance)
    except Exception: pass


@receiver(post_save,sender=CompanyLead,dispatch_uid='scoutbox-blacklist-lead-invariant')
def lead_blacklist_invariant(sender,instance,**kwargs):
    try: _block_lead(instance)
    except Exception: pass
