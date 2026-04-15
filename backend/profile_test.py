import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()
from django.conf import settings
settings.DEBUG = True
if 'cachalot' in settings.INSTALLED_APPS:
    settings.INSTALLED_APPS.remove('cachalot')
settings.CACHES['default'] = {
    'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
}

import cProfile
import pstats
import io
from django.test import RequestFactory
from listings.views import ListingViewSet

factory = RequestFactory()
request = factory.get('/api/v1/listings/', HTTP_HOST='localhost')
view = ListingViewSet.as_view({'get': 'list'})

pr = cProfile.Profile()
pr.enable()
response = view(request)
if hasattr(response, 'render'):
    response.render()
pr.disable()

from django.db import connection
print(f"Total queries: {len(connection.queries)}")
for q in connection.queries[:5]:
    print(q['sql'][:200])

s = io.StringIO()
sortby = 'tottime'
ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
ps.print_stats(30)
print(s.getvalue())
