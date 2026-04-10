# Generated manually for transactional outbox pattern

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='OutboxEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('event_name', models.CharField(db_index=True, max_length=128)),
                ('payload', models.JSONField(default=dict)),
                (
                    'status',
                    models.CharField(
                        choices=[('pending', 'Pending'), ('sent', 'Sent'), ('failed', 'Failed')],
                        db_index=True,
                        default='pending',
                        max_length=16,
                    ),
                ),
                ('retry_count', models.PositiveIntegerField(default=0)),
                ('last_error', models.TextField(blank=True)),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='outboxevent',
            index=models.Index(fields=['status', 'created_at'], name='core_outbox_status_created_idx'),
        ),
    ]
