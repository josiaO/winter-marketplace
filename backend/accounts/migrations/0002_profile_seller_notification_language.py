# Generated manually for seller push language preference.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='seller_notification_language',
            field=models.CharField(
                choices=[('sw', 'Swahili'), ('en', 'English')],
                default='sw',
                help_text='Language for seller marketplace push notifications.',
                max_length=2,
            ),
        ),
    ]
