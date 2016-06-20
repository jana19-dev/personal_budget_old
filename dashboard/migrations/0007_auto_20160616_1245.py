# -*- coding: utf-8 -*-
# Generated by Django 1.10a1 on 2016-06-16 16:45
from __future__ import unicode_literals

from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0006_auto_20160616_1158'),
    ]

    operations = [
        migrations.AddField(
            model_name='budget',
            name='bud_balance',
            field=models.DecimalField(blank=True, decimal_places=2, default=Decimal('0'), max_digits=7),
        ),
        migrations.AddField(
            model_name='budget',
            name='bud_outflows',
            field=models.DecimalField(blank=True, decimal_places=2, default=Decimal('0'), max_digits=7),
        ),
    ]