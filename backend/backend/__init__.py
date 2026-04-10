from .celery import app as celery_app

# Prevent DRF's drf_format_suffix from being registered multiple times,
# which causes a ValueError in Django 4.0+.
import django.urls.converters
from django.urls import register_converter as django_register_converter

def register_converter_idempotent(converter, type_name):
    try:
        django_register_converter(converter, type_name)
    except ValueError:
        # Already registered, skip
        pass

# Monkeypatch register_converter to be idempotent
import django.urls
import django.urls.converters
django.urls.register_converter = register_converter_idempotent
django.urls.converters.register_converter = register_converter_idempotent

__all__ = ('celery_app',)
