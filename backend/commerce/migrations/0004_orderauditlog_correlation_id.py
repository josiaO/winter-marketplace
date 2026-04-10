# Generated manually: OrderAuditLog.correlation_id for distributed tracing.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('commerce', '0003_orderauditlog'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderauditlog',
            name='correlation_id',
            field=models.CharField(
                blank=True,
                help_text='HTTP / worker correlation id for tracing checkout → payment → escrow.',
                max_length=64,
            ),
        ),
        migrations.AddIndex(
            model_name='orderauditlog',
            index=models.Index(
                fields=['correlation_id', '-created_at'],
                name='co_oal_corr_created',
            ),
        ),
    ]
