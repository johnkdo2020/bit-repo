# Generated by Django 2.2.20 on 2021-05-11 02:31

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bit_finance', '0008_bitfinanceexchange_transaction_price'),
    ]

    operations = [
        migrations.DeleteModel(
            name='BitFinanceCoinExchange',
        ),
    ]