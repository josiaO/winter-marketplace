# Generated manually for SmartDalali marketplace delivery display

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='listing',
            name='delivery_is_free',
            field=models.BooleanField(
                db_index=True,
                default=True,
                help_text='When True, buyers see free delivery; delivery_fee is ignored.',
            ),
        ),
        migrations.AddField(
            model_name='listing',
            name='delivery_fee',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Delivery charge in listing currency when delivery_is_free is False',
                max_digits=12,
                null=True,
            ),
        ),
    ]
