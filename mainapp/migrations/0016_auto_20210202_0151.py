# Generated by Django 3.1.5 on 2021-02-01 23:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mainapp', '0015_auto_20210202_0150'),
    ]

    operations = [
        migrations.AddField(
            model_name='teacher',
            name='name',
            field=models.CharField(max_length=200, null=True, verbose_name='Имя'),
        ),
        migrations.AlterField(
            model_name='teacher',
            name='name_position',
            field=models.CharField(max_length=200, verbose_name='Имя+Должность'),
        ),
    ]