# Generated by Django 2.2.20 on 2021-04-27 03:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('up_bits', '0002_auto_20210427_0319'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='upbitmarket',
            name='korean_name',
        ),
        migrations.AddField(
            model_name='upbitexchange',
            name='korean_name',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='한국 코인 이름'),
        ),
    ]