# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2018-11-17 01:10
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import utils.misc


class Migration(migrations.Migration):

    dependencies = [
        ('worktime', '0003_authorizedcookie'),
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
            ],
            bases=(utils.misc.ModelMixin, models.Model),
        ),
        migrations.RenameModel(
            'AuthorizedCookie', 'Cookie'
        ),
        migrations.AddField(
            model_name='cookie',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='worktime.User'),
        ),
        migrations.AddField(
            model_name='era',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='worktime.User'),
        ),
    ]
