#!/usr/bin/env python3
import argparse
import json
import logging
import os
import pathlib
import sys
import time
try:
  import requests
except ImportError:
  requests = None
try:
  from .models import Era, Period, Total, Adjustment
  from django.db import transaction
except ImportError:
  pass
assert sys.version_info.major >= 3, 'Python 3 required'

MODES  = ['w','p','n','s']
HIDDEN = ['s']
DATA_DIR     = pathlib.Path('~/.local/share/nbsdata').expanduser()
LOG_PATH     = DATA_DIR / 'worklog.txt'
STATUS_PATH  = DATA_DIR / 'workstatus.txt'
API_ENDPOINT = 'https://nstoler.com/worktime'
TIMEOUT = 5
USER_AGENT = 'worktime/0.1'

USAGE = """
  $ %(prog)s [options] [mode]
or
  $ %(prog)s [options] [command] [arguments]"""

DESCRIPTION = """
[mode] is a single letter (one of {})
[command] is one of the following:
  clear:  Clears the log; restarts at 0 for all modes.
  adjust: Add or subtract minutes from the recorded log.
          Give any number of arguments in the format [mode][+-][minutes]
          E.g. "p+20", "w-5", "n+100"
  status: Show the current times.
[options] is one of the optional arguments listed below.""".format(', '.join(MODES))

EPILOG = 'Note: This requires the notify2 package.'


def make_argparser():
  parser = argparse.ArgumentParser(usage=USAGE, description=DESCRIPTION, epilog=EPILOG,
                                   formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument('arguments', nargs='+', help=argparse.SUPPRESS)
  parser.add_argument('-n', '--notify', action='store_true',
    help='Report feedback to desktop notifications.')
  parser.add_argument('-O', '--no-stdout', dest='stdout', action='store_false', default=True,
    help='Don\'t print feedback to stdout.')
  parser.add_argument('-w', '--web', action='store_true',
    help='Use the website ({}) as the history log instead of local files.'.format(API_ENDPOINT))
  parser.add_argument('-u', '--url', default=API_ENDPOINT,
    help='An alternative url to use as the website API endpoint. Implies --web.')
  parser.add_argument('-k', '--skip-cert-verification', dest='verify', action='store_false',
    default=True,
    help='Don\'t verify the website TLS certificate.')
  parser.add_argument('-l', '--log', type=argparse.FileType('w'), default=sys.stderr,
    help='Print log messages to this file instead of to stderr. Warning: Will overwrite the file.')
  volume = parser.add_mutually_exclusive_group()
  volume.add_argument('-q', '--quiet', dest='volume', action='store_const', const=logging.CRITICAL,
    default=logging.WARNING)
  volume.add_argument('-v', '--verbose', dest='volume', action='store_const', const=logging.INFO)
  volume.add_argument('-D', '--debug', dest='volume', action='store_const', const=logging.DEBUG)
  return parser


def main(argv):

  parser = make_argparser()
  args = parser.parse_args(argv[1:])

  logging.basicConfig(stream=args.log, level=args.volume, format='%(message)s')

  if args.web or args.url != API_ENDPOINT:
    work_times = WorkTimesWeb(modes=MODES, hidden=HIDDEN,
                              api_endpoint=args.url, timeout=TIMEOUT, verify=args.verify)
  else:
    work_times = WorkTimesFiles(modes=MODES, hidden=HIDDEN,
                                log_path=LOG_PATH, status_path=STATUS_PATH)

  if args.arguments[0] in MODES:
    new_mode = args.arguments[0]
    old_mode, old_elapsed = work_times.switch_mode(new_mode)
    if old_mode is None or old_mode in HIDDEN or old_mode == new_mode:
      message = '(was {})'.format(old_mode)
    else:
      message = '(added {} to {})'.format(timestring(old_elapsed), old_mode)
    title, body = make_report(work_times.get_summary(), message)
    feedback(title, body, stdout=args.stdout, notify=args.notify)
  else:
    command = args.arguments[0]
    if command == 'clear':
      work_times.clear()
      feedback('Log cleared', stdout=args.stdout, notify=args.notify)
    elif command == 'adjust':
      adjustments = args.arguments[1:]
      if len(adjustments) == 0:
        fail('Error: "adjust" command requires arguments.')
      title, body = adjust(work_times, adjustments)
      feedback(title, body, stdout=args.stdout, notify=args.notify)
    elif command == 'status':
      title, body = make_report(work_times.get_summary())
      feedback(title, body, stdout=args.stdout, notify=args.notify)
    else:
      fail('Error: Invalid command {!r}.'.format(command))


def adjust(work_times, adjustments):
  messages = []
  for adjustment in adjustments:
    mode, delta = parse_adjustment(adjustment)
    work_times.add_elapsed(mode, delta)
    if delta >= 0:
      change_str = 'added to'
    else:
      change_str = 'subtracted from'
    messages.append('{} {} {}\t'.format(timestring(abs(delta)), change_str, mode))
  return 'Times adjusted', '\n'.join(messages)


def parse_adjustment(adjustment):
  fields = adjustment.split('+')
  if len(fields) == 2:
    multiplier = 1
  else:
    fields = adjustment.split('-')
    if len(fields) == 2:
      multiplier = -1
    else:
      raise WorkTimeError('Invalid adjustment string {!r}: Action must be one "+" or "-".'
                          .format(adjustment))
  mode = fields[0]
  try:
    delta = int(fields[1]) * multiplier
  except ValueError:
    raise WorkTimeError('Invalid adjustment string {!r}: Adjustment amount not a valid integer.'
                        .format(adjustment))
  return mode, delta*60


def make_report(summary, message=None):
  # Get the current status and how long it's been happening.
  title = 'Status: {} '.format(summary['current_mode'])
  if message is None:
    if summary['current_elapsed'] is not None:
      title += timestring(summary['current_elapsed'])
  else:
    title += message
  # Format a list of all the current elapsed times.
  lines = []
  for elapsed in summary['elapsed']:
    lines.append('{}:\t{}'.format(elapsed['mode'], timestring(elapsed['time'])))
  body = '\n'.join(lines)
  # If requested, calculate the ratio of the times for the specified modes.
  for ratio in summary['ratios']:
    if ratio['timespan'] == float('inf'):
      if ratio['value'] == float('inf'):
        ratio_value_str = '∞'
      else:
        ratio_value_str = '{:0.2f}'.format(ratio['value'])
      body += '\n{}:\t{}'.format(summary['ratio_str'], ratio_value_str)
  return title, body


def timestring(sec_total, format='HH:MM', abbrev=True):
  if format == 'HH:MM':
    return timestring_hhmm(sec_total)
  elif format == 'even':
    return timestring_even(sec_total, abbrev=abbrev)


def timestring_hhmm(sec_total):
  """Convert time in seconds to HH:MM string"""
  if sec_total is None:
    return 'None'
  min_total = round(sec_total / 60)
  hours = min_total // 60
  minutes = min_total % 60
  if hours:
    return "%d:%02d" % (hours, minutes)
  else:
    return str(minutes)


def timestring_even(sec_total, abbrev=True):
  if abbrev:
    hr_unit = hr_units = 'hr'
    min_unit = min_units = 'min'
  else:
    hr_unit = ' hour'
    hr_units = ' hours'
    min_unit = ' minute'
    min_units = ' minutes'
  hours = sec_total/60/60
  if hours >= 1:
    return format_rounded_num(hours, hr_unit, hr_units)
  else:
    minutes = sec_total/60
    return format_rounded_num(minutes, min_unit, min_units)


def format_rounded_num(quantity, singular, plural):
  if round(quantity, 1) == round(quantity):
    if round(quantity) == 1:
      unit = singular
    else:
      unit = plural
    return '{}{}'.format(round(quantity), unit)
  else:
    return '{:0.1f}{}'.format(quantity, plural)


def untimestring(time_str):
  if time_str is None:
    return None
  fields = time_str.split(':')
  if len(fields) == 1:
    minutes = int(fields[0])
    hours = 0
  elif len(fields) == 2:
    minutes = int(fields[1])
    hours = int(fields[0])
  return minutes*60 + hours*60*60


def feedback(title, body='', stdout=True, notify=False):
  if stdout:
    if title:
      print(title)
    if body:
      print(body)
  if notify:
    import notify2
    notice = notify2.Notification(title, body)
    try:
      notice.show()
    except notify2.UninittedError:
      notify2.init('worktime')
      notice.show()


class WorkTimes(object):
  """The parent class, agnostic to backend data store.
  Most methods are unimplemented, since they depend on the data source."""

  def __init__(self, modes=MODES, hidden=HIDDEN):
    self.modes = modes
    self.hidden = hidden

  def clear(self):
    """Erase all history and the current status."""
    raise NotImplementedError

  def switch_mode(self, new_mode):
    old_mode, old_elapsed = self.get_status()
    if old_mode is not None and old_mode not in self.hidden:
      # Save the elapsed time we spent in the old mode.
      if old_mode == new_mode:
        return old_mode, None
      now = int(time.time())
      self.add_elapsed(old_mode, old_elapsed)
    self.set_status(new_mode)
    return old_mode, old_elapsed

  def add_elapsed(self, mode, delta):
    """Add `delta` seconds to the elapsed time for `mode`."""
    elapsed = self.get_elapsed(mode)
    self.set_elapsed(mode, elapsed+delta)

  def get_summary(self, numbers='values', modes=('p', 'w')):
    summary = {}
    # Get the current status and how long it's been happening.
    current_mode, elapsed = self.get_status()
    if numbers == 'values':
      summary['current_mode'] = current_mode
      summary['current_elapsed'] = elapsed
    elif numbers == 'text':
      summary['current_mode'] = str(current_mode)
      summary['current_elapsed'] = timestring(elapsed)
    # Get all the elapsed times and add the time of the current mode to them.
    all_elapsed = self.get_all_elapsed()
    if current_mode:
      all_elapsed[current_mode] = elapsed + all_elapsed.get(current_mode, 0)
    # Format a list of all the current elapsed times.
    lines = []
    all_modes = MODES[:]
    for mode in all_elapsed.keys():
      if mode not in all_modes:
        all_modes.append(mode)
    summary['elapsed'] = []
    for mode in all_modes:
      if mode in all_elapsed and mode not in HIDDEN:
        if numbers == 'values':
          elapsed_data = {'mode':mode, 'time':all_elapsed[mode]}
        elif numbers == 'text':
          elapsed_data = {'mode':mode, 'time':timestring(all_elapsed[mode])}
        summary['elapsed'].append(elapsed_data)
    # If requested, calculate the ratio of the times for the specified modes.
    if modes and modes[0] in all_elapsed and modes[1] in all_elapsed:
      summary['ratio_str'] = '{}/{}'.format(modes[0], modes[1])
      if all_elapsed[modes[1]] == 0:
        ratio_value = float('inf')
      else:
        ratio_value = all_elapsed[modes[0]] / all_elapsed[modes[1]]
      if numbers == 'text':
        if ratio_value == float('inf'):
          ratio_value = '∞'
        else:
          ratio_value = '{:0.2f}'.format(ratio_value)
      if numbers == 'values':
        ratio_timespan = float('inf')
      elif numbers == 'text':
        ratio_timespan = 'total'
      summary['ratios'] = [{'timespan':ratio_timespan, 'value':ratio_value}]
    else:
      summary['ratio_str'] = None
      summary['ratios'] = []
    return summary

  def get_status(self):
    """Return (mode, elapsed): the current mode string, and the number of seconds we've been in it."""
    raise NotImplementedError

  #TODO: Remove, make an implementation detail?
  def set_status(self, mode=None):
    """Set the current mode to `mode`, and reset its starting time to now.
    If no mode is given, erase the current status."""
    raise NotImplementedError

  def get_elapsed(self, mode):
    """Get the total number of seconds we've spend in `mode` (NOT including the current period)."""
    raise NotImplementedError

  #TODO: Remove, make an implementation detail?
  def set_elapsed(self, mode, elapsed):
    """Set the total number of seconds we've spent in `mode` to `elapsed`."""
    raise NotImplementedError

  def get_all_elapsed(self):
    """Get the total number of seconds we've spent in every mode (NOT including the current period).
    Returns a dict mapping modes to seconds. Only modes we've spent time in will be included."""
    raise NotImplementedError

  def validate_mode(self, mode):
    """Raise a WorkTimeError if the given `mode` is not one of the canonical modes."""
    if mode is not None and mode not in self.modes:
      raise WorkTimeError('Mode {!r} is not one of the valid modes {}.'.format(mode, self.modes))


class WorkTimesFiles(WorkTimes):

  def __init__(self, modes=MODES, hidden=HIDDEN, log_path=LOG_PATH, status_path=STATUS_PATH):
    super().__init__(modes=modes, hidden=hidden)
    if isinstance(log_path, pathlib.Path):
      self.log_path = log_path
    else:
      log_path = pathlib.Path(log_path)
    if isinstance(status_path, pathlib.Path):
      self.status_path = status_path
    else:
      status_path = pathlib.Path(status_path)
    self._log = None

  def clear(self):
    self._log = None
    self._write_file({}, self.status_path)
    self._write_file({}, self.log_path)

  def get_status(self):
    data = self._read_file(self.status_path)
    if not data:
      return None, None
    else:
      if len(data.keys()) != 1:
        raise WorkTimeError('Status file {!r} contains {} statuses.'
                            .format(str(self.status_path), len(data.keys())))
      mode = list(data.keys())[0]
      start = data[mode]
      self.validate_mode(mode)
      now = int(time.time())
      return mode, now - start

  def set_status(self, mode):
    self.validate_mode(mode)
    data = {}
    if mode is not None:
      start = int(time.time())
      data[mode] = start
    self._write_file(data, self.status_path)

  def get_elapsed(self, mode):
    """Read the log file and get the elapsed time for the given mode."""
    self.validate_mode(mode)
    if self._log is None:
      self._log = self._read_log()
    return self._log.get(mode, 0)

  def set_elapsed(self, mode, elapsed):
    self.validate_mode(mode)
    if self._log is None:
      self._log = self._read_log()
    self._log[mode] = elapsed
    self._write_file(self._log, self.log_path)

  def get_all_elapsed(self):
    if self._log is None:
      self._log = self._read_log()
    return self._log

  def _read_log(self):
    """Read the elapsed times log file and store the result in the self._log cache.
    Notes on the format of the log file:
    - The order of the lines is not guaranteed (so that it can be written straight
      from a dict).
    - It is not required to contain all modes, even if zero. Any mode not in the
      file is assumed to be zero."""
    self._log = self._read_file(self.log_path)
    for mode in self._log.keys():
      if mode not in self.modes:
        raise WorkTimeError('Log file {!r} contains invalid mode {!r}.'
                            .format(str(self.log_path), mode))
    return self._log

  def _read_file(self, path):
    """Read a generic data file storing keys and integer values.
    The format is two tab-delimited columns: the key, and the value.
    This returns a key/value dict."""
    data = {}
    if os.path.isfile(path):
      try:
        with path.open() as filehandle:
          for line_num, line in enumerate(filehandle):
            fields = line.rstrip('\r\n').split()
            if len(fields) != 2:
              raise WorkTimeError('Wrong number of fields in line {} of file {!r}.'
                                  .format(line_num, str(path)))
            mode = fields[0]
            try:
              value = int(fields[1])
            except ValueError:
              raise WorkTimeError('Invalid value {!r} in file {!r}.'.format(fields[1], str(path)))
            data[mode] = value
      except OSError as error:
        raise WorkTimeError(error)
      return data
    else:
      logging.warning('Status file {!r} not found. Assuming no current status.'.format(str(path)))
      return None

  def _write_file(self, data, path):
    try:
      with path.open(mode='w') as filehandle:
        for mode, value in data.items():
          filehandle.write('{}\t{}\n'.format(mode, value))
    except OSError as error:
      raise WorkTimeError(error)


class WorkTimesDatabase(WorkTimes):

  def clear(self, new_description=''):
    # Create a new Era
    new_era = Era(current=True, description=new_description)
    # Get the current Era, if any, and end it.
    try:
      old_era = Era.objects.get(current=True)
      old_era.current = False
    except Era.DoesNotExist:
      old_era = None
    # Get the current Period, if any, and end it.
    if old_era:
      try:
        current_period = Period.objects.get(era=old_era, end=None, next=None)
        current_period.end = int(time.time())
      except Period.DoesNotExist:
        current_period = None
    else:
      current_period = None
    # Commit changes.
    with transaction.atomic():
      new_era.save()
      if old_era:
        old_era.save()
      if current_period:
        current_period.save()

  def switch_era(self, new_era_id):
    # Get the new era, make it the current one.
    try:
      new_era = Era.objects.get(pk=new_era_id)
    except Era.DoesNotExist:
      return False
    new_era.current = True
    # Get the old era, make it not current anymore.
    old_era = Era.objects.get(current=True)
    old_era.current = False
    # Get the current Period and end it.
    try:
      current_period = Period.objects.get(era=old_era, end=None, next=None)
      current_period.end = int(time.time())
    except Period.DoesNotExist:
      current_period = None
    # Commit changes.
    with transaction.atomic():
      old_era.save()
      new_era.save()
      if current_period:
        current_period.save()
    return True

  def get_status(self, era=None):
    # Get the current Era, if not already given.
    if era is None:
      try:
        era = Era.objects.get(current=True)
      except Era.DoesNotExist:
        return None, None
    # Get the current Period.
    try:
      current_period = Period.objects.get(era=era, end=None, next=None)
    except Period.DoesNotExist:
      return None, None
    # Calculate and return mode, elapsed
    self.validate_mode(current_period.mode)
    now = int(time.time())
    return current_period.mode, now - current_period.start

  def switch_mode(self, mode):
    # Note: If mode is None, this will just create a new Period where the mode is None.
    self.validate_mode(mode)
    # Get the current Era, or create one if it doesn't exist.
    era, created = Era.objects.get_or_create(current=True)
    # Create a new Period.
    now = int(time.time())
    new_period = Period(era=era, mode=mode, start=now)
    # Get the old Period, if any.
    try:
      old_period = Period.objects.get(era=era, end=None, next=None)
    except Period.DoesNotExist:
      old_period = None
    if old_period:
      # If there was an old Period, end it, and add its elapsed time to the Total.
      old_period.end = now
      new_period.prev = old_period
      if mode is None:
        logging.info('No mode.')
        total = None
      else:
        total, created = Total.objects.get_or_create(era=era, mode=old_period.mode)
        total.elapsed += old_period.elapsed
    else:
      total = None
    # Commit changes.
    with transaction.atomic():
      new_period.save()
      if old_period:
        old_period.save()
      if total:
        total.save()
    if old_period:
      return old_period.mode, old_period.elapsed
    else:
      return None, None

  def get_elapsed(self, mode):
    if mode is None:
      return None
    self.validate_mode(mode)
    # Get the current Era.
    try:
      era = Era.objects.get(current=True)
    except Era.DoesNotExist:
      return 0
    # Get the current Period.
    now = int(time.time())
    try:
      current_period = Period.objects.get(era=era, mode=mode, end=None, next=None)
      elapsed_period = now - current_period.start
    except Period.DoesNotExist:
      elapsed_period = 0
    # Get the Total for this mode.
    try:
      total = Total.objects.get(era=era, mode=mode)
      elapsed_total = total.elapsed
    except Total.DoesNotExist:
      elapsed_total = 0
    return elapsed_period + elapsed_total

  def add_elapsed(self, mode, delta):
    assert mode is not None, mode
    self.validate_mode(mode)
    # Get the current Era.
    try:
      era = Era.objects.get(current=True)
    except Era.DoesNotExist:
      return False
    now = int(time.time())
    # Create an Adjustment, and add to the Total for this mode.
    adjustment = Adjustment(era=era, mode=mode, delta=delta, timestamp=now)
    total, created = Total.objects.get_or_create(era=era, mode=mode)
    total.elapsed += delta
    # Commit changes.
    with transaction.atomic():
      adjustment.save()
      total.save()
    return True

  def get_all_elapsed(self):
    try:
      era = Era.objects.get(current=True)
    except Era.DoesNotExist:
      return {}
    data = {}
    for total in Total.objects.filter(era=era):
      data[total.mode] = total.elapsed
    return data

  def get_summary(self, numbers='values', modes=('p', 'w'), timespans=(6*60*60,)):
    """Augment the default summary with a ratio for just the last `ratio` seconds."""
    summary = super().get_summary(numbers=numbers, modes=modes)
    try:
      era = Era.objects.get(current=True)
    except Era.DoesNotExist:
      return summary
    summary['era'] = era.description
    ratios = self._get_recent_ratios(timespans, numbers, modes, era=era)
    summary['ratios'].extend(ratios)
    return summary

  def _get_recent_ratios(self, timespans, numbers='values', modes=('p', 'w'), era=None):
    """Get ratio for only the last `timespan` seconds."""
    ratios = []
    if era is None:
      try:
        era = Era.objects.get(current=True)
      except Era.DoesNotExist:
        return None, None
    now = int(time.time())
    cutoffs = [now-timespan for timespan in timespans]
    min_cutoff = min(cutoffs)
    periods = Period.objects.filter(era=era, end__gte=min_cutoff).order_by('start')
    try:
      current_period = Period.objects.get(era=era, end=None, next=None)
    except Period.DoesNotExist:
      current_period = None
    totals = []
    for i in range(len(timespans)):
      totals.append([0, 0])
    for period in list(periods) + [current_period]:
      for i in 0, 1:
        for c, cutoff in enumerate(cutoffs):
          if period and (period.end is None or period.end >= cutoff) and period.mode == modes[i]:
            if period.start >= cutoff:
              totals[c][i] += period.elapsed
            else:
              totals[c][i] += period.elapsed - (cutoff-period.start)
    #TODO: If an adjustment happened earlier than this cutoff, but during a period that ended after
    #      it, that might cause unnatural-feeling results. E.g. Maybe I left it on 'w' for an hour,
    #      but took a 30 min break and forgot to turn it off. So I did an adjustment of -30, but
    #      then left it on 'w' because I was back. This could possibly make a really weird ratio.
    for adjustment in Adjustment.objects.filter(era=era, timestamp__gte=min_cutoff):
      for i in 0, 1:
        for c, cutoff in enumerate(cutoffs):
          if adjustment.timestamp >= cutoff and adjustment.mode == modes[i]:
            # Expand the adjustment backward into a "virtual period" as `delta` long, ending when
            # the adjustment was made. Then, only count the part of the adjustment before the period.
            time_btwn_adj_and_cutoff = adjustment.timestamp - cutoff
            if abs(adjustment.delta) > time_btwn_adj_and_cutoff:
              sign = int(adjustment.delta / abs(adjustment.delta))
              totals[c][i] += sign * time_btwn_adj_and_cutoff
            else:
              totals[c][i] += adjustment.delta
    for c, timespan in enumerate(timespans):
      ratio = {}
      logging.info('Totals for last {}s: {} in {}, {} in {}.'
                   .format(timespan, totals[c][0], modes[0], totals[c][1], modes[1]))
      # Store the value of the ratio.
      if totals[c][1] == 0:
        if numbers == 'values':
          ratio['value'] = float('inf')
        elif numbers == 'text':
          ratio['value'] = '∞'
      else:
        ratio['value'] = totals[c][0]/totals[c][1]
        if numbers == 'text':
          ratio['value'] = '{:0.2f}'.format(ratio['value'])
      # Store the period of time the recent ratio is for.
      if numbers == 'values':
        ratio['timespan'] = timespan
      elif numbers == 'text':
        ratio['timespan'] = timestring(timespan, format='even', abbrev=True)
      ratios.append(ratio)
    return ratios


class WorkTimesWeb(WorkTimes):

  def __init__(self, modes=MODES, hidden=HIDDEN,
               api_endpoint=API_ENDPOINT, timeout=TIMEOUT, verify=True):
    super().__init__(modes=modes, hidden=hidden)
    self.api_endpoint = api_endpoint
    self.timeout = timeout
    self.verify = verify

  #TODO: Finish implementing rest of the methods.

  def clear(self):
    self._make_request('/clear', method='post', timeout=self.timeout)

  def switch_mode(self, new_mode):
    # Override this method in the parent, since it's a special case with web.
    self.validate_mode(new_mode)
    # Get the old status.
    old_mode, old_elapsed = self.get_status()
    # Make the switch.
    params = {'mode':new_mode}
    self._make_request('/switch', method='post', data=params, timeout=self.timeout)
    return old_mode, old_elapsed

  def add_elapsed(self, mode, delta):
    # Override this method in the parent, since it's a special case with web.
    self.validate_mode(mode)
    params = {'mode':mode}
    if delta < 0:
      params['subtract'] = abs(delta)//60
    else:
      params['add'] = delta//60
    self._make_request('/adjust', method='post', data=params, timeout=self.timeout)

  def get_summary(self, numbers='values'):
    # Override this method in the parent, since it's a special case with web.
    return self._make_request('?format=json&numbers={}'.format(numbers),
                              format='json', timeout=self.timeout)

  def get_status(self):
    summary = self.get_summary()
    return summary['current_mode'], summary['current_elapsed']

  def get_all_elapsed(self):
    summary = self.get_summary()
    all_elapsed = {}
    for elapsed in summary['elapsed']:
      all_elapsed[elapsed['mode']] = elapsed['time']
    return all_elapsed

  def _make_request(self, url_end, method='get', format='text', **kwargs):
    if 'headers' in kwargs:
      kwargs['headers']['User-Agent'] = USER_AGENT
    else:
      kwargs['headers'] = {'User-Agent':USER_AGENT}
    if not self.verify:
      kwargs['verify'] = False
    try:
      if method == 'get':
        response = requests.get(self.api_endpoint+url_end, **kwargs)
      elif method == 'post':
        response = requests.post(self.api_endpoint+url_end, **kwargs)
    except requests.exceptions.RequestException as error:
      raise WorkTimeError(error)
    if response.status_code != 200:
      raise WorkTimeError('Error making request: response code {} ({}).'
                          .format(response.status_code, response.reason))
    if format == 'text':
      return response.text
    elif format == 'json':
      return response.json()


class WorkTimeError(Exception):
  def __init__(self, data):
    self.data = data
    if isinstance(self.data, Exception):
      self.exception = self.data
      self.message = '{}: {}'.format(type(self.exception).__name__, str(self.exception))
    elif isinstance(self.data, str):
      self.message = self.data
    self.args = (self.message,)
  def __str__(self):
    return self.message
  def __repr__(self):
    return '{}({})'.format(type(self).__name__, repr(self.data))


def fail(message):
  logging.critical(message)
  if __name__ == '__main__':
    sys.exit(1)
  else:
    raise Exception('Unrecoverable error')


if __name__ == '__main__':
  try:
    sys.exit(main(sys.argv))
  except BrokenPipeError:
    pass
