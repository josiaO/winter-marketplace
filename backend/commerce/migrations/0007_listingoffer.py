# Generated manually

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('commerce', '0006_sellerwithdrawalrequest'),
        ('listings', '0005_alter_listing_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='ListingOffer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('awaiting_seller', 'Awaiting seller'),
                            ('awaiting_buyer', 'Awaiting buyer'),
                            ('accepted', 'Accepted'),
                            ('declined', 'Declined'),
                            ('expired', 'Expired'),
                            ('superseded', 'Superseded'),
                            ('fulfilled', 'Fulfilled at checkout'),
                        ],
                        db_index=True,
                        default='awaiting_seller',
                        max_length=20,
                    ),
                ),
                ('listed_price', models.DecimalField(decimal_places=2, max_digits=14)),
                ('current_amount', models.DecimalField(decimal_places=2, max_digits=14)),
                ('buyer_note', models.TextField(blank=True)),
                ('seller_note', models.TextField(blank=True)),
                ('last_actor', models.CharField(blank=True, max_length=10)),
                ('counter_round', models.PositiveSmallIntegerField(default=0)),
                ('accepted_until', models.DateTimeField(blank=True, null=True)),
                (
                    'buyer',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='listing_offers_as_buyer',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'listing',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='offers',
                        to='listings.listing',
                    ),
                ),
                (
                    'seller',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='listing_offers_as_seller',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='listingoffer',
            index=models.Index(fields=['buyer', 'status'], name='commerce_li_buyer_i_idx'),
        ),
        migrations.AddIndex(
            model_name='listingoffer',
            index=models.Index(fields=['listing', 'buyer', 'status'], name='commerce_li_listing_idx'),
        ),
    ]
