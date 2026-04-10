# PayoutDestination: at most one is_default=True per user

from django.db import migrations, models


def dedupe_default_destinations(apps, schema_editor):
    PayoutDestination = apps.get_model('escrow_engine', 'PayoutDestination')
    seen_users = set()
    # Keep the lowest pk as default per user when multiple defaults exist
    for row in (
        PayoutDestination.objects.filter(is_default=True)
        .order_by('user_id', 'id')
        .values_list('id', 'user_id')
    ):
        dest_id, user_id = row
        if user_id in seen_users:
            PayoutDestination.objects.filter(pk=dest_id).update(is_default=False)
        else:
            seen_users.add(user_id)


class Migration(migrations.Migration):

    dependencies = [
        ('escrow_engine', '0002_api_key_and_transaction_link'),
    ]

    operations = [
        migrations.RunPython(dedupe_default_destinations, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='payoutdestination',
            constraint=models.UniqueConstraint(
                condition=models.Q(is_default=True),
                fields=('user',),
                name='escrow_payoutdest_one_default_per_user',
            ),
        ),
    ]
