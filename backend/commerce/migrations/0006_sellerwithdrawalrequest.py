# Generated manually

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('commerce', '0005_rename_co_oal_order_created_commerce_or_order_i_497b63_idx_and_more'),
        ('marketplace', '0006_sellerprofile_store_banner'),
    ]

    operations = [
        migrations.CreateModel(
            name='SellerWithdrawalRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=14)),
                ('currency', models.CharField(default='TZS', max_length=3)),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('pending', 'Pending'),
                            ('completed', 'Completed'),
                            ('rejected', 'Rejected'),
                        ],
                        db_index=True,
                        default='pending',
                        max_length=20,
                    ),
                ),
                ('seller_note', models.CharField(blank=True, max_length=500)),
                ('admin_note', models.CharField(blank=True, max_length=500)),
                (
                    'payout_method',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='withdrawal_requests',
                        to='marketplace.sellerpaymentmethod',
                    ),
                ),
                (
                    'seller',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='withdrawal_requests',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'verbose_name': 'Seller withdrawal request',
                'verbose_name_plural': 'Seller withdrawal requests',
                'ordering': ['-created_at'],
            },
        ),
    ]
