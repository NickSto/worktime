from django.db import models
from utils import ModelMixin

class Status(ModelMixin, models.Model):
  mode = models.CharField(max_length=63)
  start = models.BigIntegerField()

class Elapsed(ModelMixin, models.Model):
  mode = models.CharField(max_length=63)
  elapsed = models.IntegerField()

