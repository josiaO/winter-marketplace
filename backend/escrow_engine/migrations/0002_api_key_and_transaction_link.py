# Generated manually for escrow_engine hardening

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('escrow_engine', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='APIKey',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('key_hash', models.CharField(db_index=True, max_length=64, unique=True)),
                ('is_active', models.BooleanField(default=True)),
                ('scopes', models.JSONField(blank=True, default=list, help_text='List of strings: read, write, pay, refund, release. read=list/retrieve; write=create transaction + open dispute; pay/refund/release=matching actions.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_used_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'API Key',
                'verbose_name_plural': 'API Keys',
            },
        ),
        migrations.AddField(
            model_name='transaction',
            name='created_by_api_key',
            field=models.ForeignKey(blank=True, help_text='Developer API key that created this transaction (if any).', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='transactions', to='escrow_engine.apikey'),
        ),
    ]
