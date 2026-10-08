from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Opportunity, CompanyLead, Contact
from .services.focus import assign_focus


def _assign(sender, instance, created, **kwargs):
    if not getattr(instance,'pk',None):
        return
    # A real existing Focus is stable. New rows are classified against that taxonomy;
    # rows left blank because the local classifier was temporarily unavailable get a
    # cheap retry on a later enrichment/health save without rebuilding everyone else.
    if not created and str(getattr(instance,'focus','') or '').strip():
        return
    try:
        assign_focus(instance)
    except Exception:
        # Focus is a convenience facet and must never make discovery/contact persistence fail.
        pass

post_save.connect(_assign, sender=Opportunity, dispatch_uid='scoutbox-focus-opportunity')
post_save.connect(_assign, sender=CompanyLead, dispatch_uid='scoutbox-focus-hidden-lead')
post_save.connect(_assign, sender=Contact, dispatch_uid='scoutbox-focus-contact')
