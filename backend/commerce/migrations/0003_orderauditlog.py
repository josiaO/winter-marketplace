# Generated manually for commerce hardening (OrderAuditLog).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('commerce', '0002_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='OrderAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('action', models.CharField(db_index=True, max_length=64)),
                ('from_status', models.CharField(blank=True, max_length=32)),
                ('to_status', models.CharField(blank=True, max_length=32)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('actor', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='commerce_order_audit_entries',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('order', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='audit_logs',
                    to='commerce.order',
                )),
            ],
            options={
                'verbose_name': 'Order audit log',
                'verbose_name_plural': 'Order audit logs',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='orderauditlog',
            index=models.Index(fields=['order', '-created_at'], name='co_oal_order_created'),
        ),
        migrations.AddIndex(
            model_name='orderauditlog',
            index=models.Index(fields=['action', '-created_at'], name='co_oal_action_created'),
        ),
    ]
