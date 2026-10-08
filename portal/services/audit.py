from portal.models import AuditLog


def _object_title(obj):
    if obj is None:
        return ''
    for field in ('email_subject','title','name','display_name','company','label'):
        value=getattr(obj,field,None)
        if value and str(value).strip():
            return str(value).strip()[:300]
    opportunity=getattr(obj,'opportunity',None)
    if opportunity is not None:
        bits=[str(getattr(opportunity,'company','') or '').strip(),str(getattr(opportunity,'title','') or '').strip()]
        return ' — '.join(x for x in bits if x)[:300]
    return ''


def log(action, request=None, obj=None, summary='', metadata=None):
    actor='system'
    if request is not None and getattr(request,'user',None) and request.user.is_authenticated:
        actor=request.user.email or request.user.username
    data=dict(metadata or {})
    title=_object_title(obj)
    if title and not data.get('object_title'):
        data['object_title']=title
    AuditLog.objects.create(actor=actor, action=action, object_type=obj.__class__.__name__ if obj else '', object_id=str(getattr(obj,'pk','')) if obj else '', summary=summary, metadata=data)
