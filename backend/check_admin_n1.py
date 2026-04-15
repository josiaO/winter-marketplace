import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from django.contrib.admin.sites import site
from django.db import models

for model, admin_class in site._registry.items():
    has_fks = any(isinstance(f, (models.ForeignKey, models.OneToOneField)) for f in model._meta.fields)
    has_list_select_related = getattr(admin_class, 'list_select_related', False)
    
    if has_fks and not has_list_select_related:
        print(f"Model {model.__name__} in {admin_class.__module__} has FKs but no list_select_related!")
