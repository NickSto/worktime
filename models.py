import logging
import time
from django.db import models
from django.utils import timezone as utils_timezone
from utils import ModelMixin
log = logging.getLogger(__name__)
MODE_MAX_LEN = 63

#TODO: Let's have a button or something to create a demo `Era` (name it "Big Project" or
#      something) that shows off all the features.

class User(ModelMixin, models.Model):
  name = models.CharField(max_length=255)

class Era(ModelMixin, models.Model):
  user = models.ForeignKey(User, models.SET_NULL, null=True, blank=True)
  description = models.CharField(max_length=255)
  current = models.BooleanField()

class Period(ModelMixin, models.Model):
  mode = models.CharField(max_length=MODE_MAX_LEN, null=True, blank=True)
  start = models.BigIntegerField()
  end = models.BigIntegerField(null=True, blank=True)
  prev = models.OneToOneField('self', models.SET_NULL, null=True, blank=True, related_name='next')
  era = models.ForeignKey(Era, models.SET_NULL, null=True, blank=True)
  @property
  def elapsed(self):
    if self.end:
      return self.end - self.start
    else:
      return int(time.time()) - self.start

class Adjustment(ModelMixin, models.Model):
  mode = models.CharField(max_length=MODE_MAX_LEN)
  delta = models.IntegerField()
  timestamp = models.BigIntegerField()
  era = models.ForeignKey(Era, models.SET_NULL, null=True, blank=True)

class Total(ModelMixin, models.Model):
  """The total number of seconds we've spent in each mode, including all Adjustments, but NOT
  the current Period."""
  mode = models.CharField(max_length=MODE_MAX_LEN)
  elapsed = models.IntegerField(default=0)
  era = models.ForeignKey(Era, models.SET_NULL, null=True, blank=True)

class Cookie(ModelMixin, models.Model):
  user = models.ForeignKey(User, models.SET_NULL, null=True, blank=True)
  name = models.CharField(max_length=128)
  value = models.CharField(max_length=128)
  def __str__(self):
    return self.value
  def __repr__(self):
    return '{}(name={!r}, value={!r})'.format(type(self).__name__, self.name, self.value)
