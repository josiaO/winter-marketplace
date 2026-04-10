from django.db import models
import uuid
import string
import secrets

def generate_short_code():
    length = 6
    chars = string.ascii_letters + string.digits
    while True:
        code = ''.join(secrets.choice(chars) for _ in range(length))
        if not ShortLink.objects.filter(code=code).exists():
            return code

class ShortLink(models.Model):
    target_url = models.URLField(max_length=2000)
    code = models.CharField(max_length=10, unique=True, default=generate_short_code)
    created_at = models.DateTimeField(auto_now_add=True)
    visit_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.code} -> {self.target_url}"
