from django.contrib import admin

from . import models


# Register the portal's concrete models for the optional Django admin.
# Abstract base classes (for example SingletonModel) have model metadata but
# cannot be registered with admin, so explicitly skip them.
for name in dir(models):
    obj = getattr(models, name)

    if not isinstance(obj, type) or not hasattr(obj, "_meta"):
        continue
    if getattr(obj._meta, "app_label", None) != "portal":
        continue
    if obj._meta.abstract:
        continue

    try:
        admin.site.register(obj)
    except admin.sites.AlreadyRegistered:
        pass
