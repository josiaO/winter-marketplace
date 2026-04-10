# GatewayEvent idempotency + API key hardening fields

import uuid

import django.db.models.deletion
from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):

    dependencies = [
        ('escrow_engine', '0003_payoutdestination_one_default'),
    ]

    operations = [
        migrations.AddField(
            model_name='apikey',
            name='ip_allowlist',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Optional list of IP strings; empty = no restriction.',
            ),
        ),
        migrations.AddField(
            model_name='apikey',
            name='rate_limit_per_minute',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Max requests per minute for this key; blank = default throttle.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='apikey',
            name='expires_at',
            field=models.DateTimeField(
                blank=True,
                help_text='Key invalid after this time (UTC). Blank = no expiry.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='apikey',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, default=timezone.now),
            preserve_default=False,
        ),
        migrations.CreateModel(
            name='GatewayEvent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('provider', models.CharField(db_index=True, max_length=50)),
                ('event_id', models.CharField(max_length=255)),
                ('payload', models.JSONField(blank=True, default=dict)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('pending', 'Pending'),
                            ('processed', 'Processed'),
                            ('duplicate', 'Duplicate'),
                            ('failed', 'Failed'),
                        ],
                        db_index=True,
                        default='pending',
                        max_length=20,
                    ),
                ),
                ('error_message', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'transaction',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='gateway_events',
                        to='escrow_engine.transaction',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Gateway event',
                'verbose_name_plural': 'Gateway events',
            },
        ),
        migrations.AddConstraint(
            model_name='gatewayevent',
            constraint=models.UniqueConstraint(
                fields=('provider', 'event_id'),
                name='escrow_gatewayevent_provider_event_id_uniq',
            ),
        ),
        migrations.AddIndex(
            model_name='gatewayevent',
            index=models.Index(fields=['provider', 'status'], name='escrow_gate_provide_2f5c8e_idx'),
        ),
    ]
