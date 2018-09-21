# -*- coding: utf-8 -*-
# Generated by Django 1.11.11 on 2018-09-21 07:44
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import utils.misc


class Migration(migrations.Migration):

    dependencies = [
        ('worktime', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Adjustment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mode', models.CharField(max_length=63)),
                ('delta', models.IntegerField()),
                ('timestamp', models.BigIntegerField()),
            ],
            bases=(utils.misc.ModelMixin, models.Model),
        ),
        migrations.CreateModel(
            name='Era',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(max_length=255)),
                ('current', models.BooleanField()),
            ],
            bases=(utils.misc.ModelMixin, models.Model),
        ),
        migrations.CreateModel(
            name='Period',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mode', models.CharField(blank=True, max_length=63, null=True)),
                ('start', models.BigIntegerField()),
                ('end', models.BigIntegerField(blank=True, null=True)),
                ('era', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='worktime.Era')),
                ('prev', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='next', to='worktime.Period')),
            ],
            bases=(utils.misc.ModelMixin, models.Model),
        ),
        migrations.CreateModel(
            name='Total',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mode', models.CharField(max_length=63)),
                ('elapsed', models.IntegerField(default=0)),
                ('era', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='worktime.Era')),
            ],
            bases=(utils.misc.ModelMixin, models.Model),
        ),
        migrations.DeleteModel(
            name='Elapsed',
        ),
        migrations.DeleteModel(
            name='Status',
        ),
        migrations.AddField(
            model_name='adjustment',
            name='era',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='worktime.Era'),
        ),
    ]