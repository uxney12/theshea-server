# Generated by Django 5.1.3 on 2025-02-25 09:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0033_sku_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='collection',
            name='date',
            field=models.DateField(blank=True, null=True),
        ),
    ]
