# Generated by Django 5.1.3 on 2025-03-03 03:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0041_order_status_receipt_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='material',
            name='stock_max',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='material',
            name='stock_min',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='order',
            name='total_quantity',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='receipt',
            name='total_quantity',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
