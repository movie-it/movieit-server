# Generated by Django 3.1.6 on 2021-02-06 01:42

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('movies', '0003_auto_20210205_2120'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='record',
            options={'ordering': ('created_at',)},
        ),
    ]