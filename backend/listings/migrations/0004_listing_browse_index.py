from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0003_listing_delivery_fields'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='listing',
            index=models.Index(
                fields=['is_published', 'category', 'owner'],
                name='listings_list_pub_cat_owner',
            ),
        ),
    ]
