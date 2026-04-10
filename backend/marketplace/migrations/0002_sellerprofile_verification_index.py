from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0001_initial'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='sellerprofile',
            index=models.Index(
                fields=['verification_status', 'is_active'],
                name='market_seller_verif_act_idx',
            ),
        ),
    ]
