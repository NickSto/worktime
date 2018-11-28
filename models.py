import logging
import time
from django.db import models
from django.utils import timezone as utils_timezone
from utils import ModelMixin
log = logging.getLogger(__name__)
MODE_MAX_LEN = 63


#TODO: Persistent preferences system.
#      Maybe just add fields to the User model?
#TODO: Link complementary `Adjustment`s where time is taken from one mode and added to another.
#      Add a `OneToOneField` to `Adjustment` linking pairs of adjustments.
#      - or maybe make a new `Adjustment` type for a move from one mode to another.
#      Add UI for "Move [ ] from [ ] to [ ]".
#      - might have to progressively enhance a set of radio buttons for selecting the from mode.
#        - can't style radio buttons to look like the other buttons on the page.
#        - might have to leave the ugly radios there in the javascript-free version
#      Represent the link in the summary data structure.
#      Display in the Adjustments bar.
#      - use the color of the mode being added to
#      - maybe special text, like "w <- 4 <- p"

class User(ModelMixin, models.Model):
  name = models.CharField(max_length=255)
  def __repr__(self):
    return '{}(id={!r}, name={!r})'.format(type(self).__name__, self.id, self.name)
  def __str__(self):
    return self.name

class Era(ModelMixin, models.Model):
  user = models.ForeignKey(User, models.SET_NULL, null=True, blank=True)
  description = models.CharField(max_length=255)
  current = models.BooleanField()
  def __repr__(self):
    return ('{}(user={!r}, current={!r}, description={!r})'
            .format(type(self).__name__, self.user, self.current, self.description))

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
    return ('{}(user={!r}, name={!r}, value={!r})'
            .format(type(self).__name__, self.user, self.name, self.value))
