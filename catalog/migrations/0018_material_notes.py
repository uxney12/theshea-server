# Generated by Django 5.1.3 on 2025-02-13 14:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0017_alter_material_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='material',
            name='notes',
            field=models.CharField(blank=True, max_length=10000, null=True),
        ),
    ]
