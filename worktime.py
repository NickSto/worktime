#!/usr/bin/env python3
import argparse
import collections
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
  from .models import User, Era, Period, Total, Adjustment
  from django.db import transaction
except ImportError:
  pass
assert sys.version_info.major >= 3, 'Python 3 required'

MODES  = ['w','p','n','s']
MODES_META = {
  'w': {'abbrev':'w', 'name':'work', 'hidden':False, 'opposite':'p'},
  'p': {'abbrev':'p', 'name':'play', 'hidden':False, 'opposite':'w'},
  'n': {'abbrev':'n', 'name':'neutral', 'hidden':False, 'opposite':None},
  's': {'abbrev':'s', 'name':'stopped', 'hidden':True, 'opposite':None},
}
HIDDEN = [mode for mode, meta in MODES_META.items() if meta['hidden']]
RATIO_MODES = ('p', 'w')
DATA_DIR     = pathlib.Path('~/.local/share/nbsdata').expanduser()
LOG_PATH     = DATA_DIR / 'worklog.txt'
STATUS_PATH  = DATA_DIR / 'workstatus.txt'
API_ENDPOINT = 'https://nstoler.com/worktime'
COOKIE_NAME  = 'visitors_v1'
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
  parser.add_argument('-A', '--no-abbrev', dest='abbrev', action='store_false', default=True,
    help='Don\'t abbreviate mode names (show "work" instead of "w").')
  parser.add_argument('-w', '--web', action='store_true',
    help='Use the website ({}) as the history log instead of local files.'.format(API_ENDPOINT))
  parser.add_argument('-s', '--sync', action='store_true',
    help='When using --web, sync the local state files with the web state. This will always '
         'overwrite the local state, and will never overwrite the web state with the local one.')
  parser.add_argument('-S', '--summary',
    help='When using --web, write the raw summary data to this file (in JSON).')
  parser.add_argument('-c', '--cookie',
    help='Authorization cookie to use when in --web mode.')
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
    if args.sync:
      status_path = STATUS_PATH
      log_path = LOG_PATH
    else:
      status_path = None
      log_path = None
    work_times = WorkTimesWeb(modes=MODES, hidden=HIDDEN, abbrev=args.abbrev, api_endpoint=args.url,
                              timeout=TIMEOUT, verify=args.verify, cookie=args.cookie,
                              status_path=status_path, log_path=log_path, summary_path=args.summary)
  else:
    work_times = WorkTimesFiles(modes=MODES, hidden=HIDDEN, abbrev=args.abbrev,
                                log_path=LOG_PATH, status_path=STATUS_PATH)

  if args.arguments[0] in MODES:
    new_mode = args.arguments[0]
    old_mode, old_elapsed = work_times.switch_mode(new_mode)
    if old_mode is None or old_mode in HIDDEN or old_mode == new_mode:
      message = '(was {})'.format(old_mode)
    else:
      message = '(added {} to {})'.format(timestring(old_elapsed), old_mode)
    title, body = make_report(work_times, message)
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
      title, body = make_report(work_times)
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


def make_report(work_times, message=None):
  # Get the current status and how long it's been happening.
  mode, elapsed = work_times.get_status()
  title = 'Status: {} '.format(mode)
  if message is None:
    if elapsed is not None:
      title += timestring(elapsed)
  else:
    title += message
  # Format a list of all the current elapsed times.
  lines = []
  all_elapsed = work_times.get_all_elapsed()
  for mode, elapsed in all_elapsed.items():
    lines.append('{}:\t{}'.format(mode, timestring(elapsed)))
  body = '\n'.join(lines)
  # If requested, calculate the ratio of the times for the specified modes.
  ratio = work_times.get_ratio(*RATIO_MODES, all_elapsed=all_elapsed)
  if ratio is None:
    return title, body
  if ratio == float('inf'):
    ratio_value_str = '∞'
  else:
    ratio_value_str = '{:0.2f}'.format(ratio)
  ratio_label = '{}/{}'.format(*RATIO_MODES)
  body += '\n{}:\t{}'.format(ratio_label, ratio_value_str)
  return title, body


def get_mode_name(mode, abbrev=False):
  if abbrev:
    return mode
  elif mode in MODES_META:
    return MODES_META[mode].get('name', mode)
  else:
    return mode


def format_timespan(seconds, numbers, label_smallest=True):
  if numbers == 'values':
    return seconds
  elif numbers == 'text':
    return timestring(seconds, label_smallest=label_smallest)


def timestring(sec_total, format='HH:MM', abbrev=True, label_smallest=False):
  if format == 'HH:MM':
    return timestring_hhmm(sec_total, abbrev=abbrev, label_smallest=label_smallest)
  elif format == 'even':
    return timestring_even(sec_total, abbrev=abbrev)


def timestring_hhmm(sec_total, abbrev=True, label_smallest=False):
  """Convert time in seconds to HH:MM string"""
  if sec_total is None:
    return 'None'
  if sec_total < 0:
    sign = '-'
  else:
    sign = ''
  min_total = round(abs(sec_total) / 60)
  hours = min_total // 60
  minutes = min_total % 60
  if hours:
    return '{}{:d}:{:02d}'.format(sign, hours, minutes)
  else:
    if label_smallest:
      if abbrev:
        return '{}{}min'.format(sign, minutes)
      elif minutes == 1:
        return sign+'1 minute'
      else:
        return '{}{} minutes'.format(sign, minutes)
    else:
      return sign+str(minutes)


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

  def __init__(self, modes=MODES, hidden=HIDDEN, abbrev=True):
    self.modes = modes
    self.hidden = hidden
    self.abbrev = abbrev

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

  #TODO: Separate display stuff from core logic.
  #      Or maybe remove entirely? There may not be much of a point to a generic get_summary().
  #      It's very difficult to efficiently serve the needs of all possible consumers of this data.
  #      Instead, the consumer should use individual methods for their purpose.
  #      Proposal: Maybe keep, but pass in a list of stats the user desires.
  def get_summary(self, numbers='values', modes=RATIO_MODES):
    summary = {}
    # Get the current status and how long it's been happening.
    current_mode, elapsed = self.get_status()
    if numbers == 'values':
      summary['current_mode'] = current_mode
      summary['current_elapsed'] = elapsed
    elif numbers == 'text':
      summary['current_mode'] = str(current_mode)
      summary['current_elapsed'] = timestring(elapsed)
    summary['current_mode_name'] = get_mode_name(summary['current_mode'], abbrev=self.abbrev)
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
        elapsed_data['mode_name'] = get_mode_name(elapsed_data['mode'], abbrev=self.abbrev)
        summary['elapsed'].append(elapsed_data)
    # If requested, calculate the ratio of the times for the specified modes.
    if modes:
      if self.abbrev:
        summary['ratio_str'] = '{}/{}'.format(modes[0], modes[1])
      else:
        mode0 = get_mode_name(modes[0], abbrev=self.abbrev)
        mode1 = get_mode_name(modes[1], abbrev=self.abbrev)
        summary['ratio_str'] = '{}/{}'.format(mode0, mode1)
      ratio_value = self.get_ratio(modes[0], modes[1], all_elapsed=all_elapsed)
      if numbers == 'text':
        if ratio_value is None:
          ratio_value = 'None'
        elif ratio_value == float('inf'):
          ratio_value = '∞'
        else:
          ratio_value = '{:0.2f}'.format(ratio_value)
        ratio_timespan = 'total'
      elif numbers == 'values':
        ratio_timespan = float('inf')
      summary['ratios'] = [{'timespan':ratio_timespan, 'value':ratio_value}]
    else:
      summary['ratio_str'] = None
      summary['ratios'] = []
    return summary

  def get_ratio(self, num_mode, denom_mode, all_elapsed=None):
    if all_elapsed is None:
      all_elapsed = self.get_all_elapsed()
    if num_mode not in all_elapsed and denom_mode not in all_elapsed:
      return None
    elif all_elapsed.get(denom_mode, 0) == 0:
      return float('inf')
    else:
      return all_elapsed.get(num_mode, 0) / all_elapsed.get(denom_mode, 0)

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

  def __init__(self, modes=MODES, hidden=HIDDEN, abbrev=True,
               log_path=LOG_PATH, status_path=STATUS_PATH):
    super().__init__(modes=modes, hidden=hidden, abbrev=abbrev)
    if isinstance(log_path, pathlib.Path):
      self.log_path = log_path
    else:
      self.log_path = pathlib.Path(log_path)
    if isinstance(status_path, pathlib.Path):
      self.status_path = status_path
    else:
      self.status_path = pathlib.Path(status_path)
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

  def write_summary(self, summary, current_inclusive=False):
    # Write the given summary data to the files.
    now = int(time.time())
    current_mode = summary['current_mode']
    if current_mode is None:
      status = {}
    else:
      mode_start = now-summary['current_elapsed']
      status = {current_mode:mode_start}
    self._write_file(status, self.status_path)
    self._log = {}
    for elapsed_data in summary['elapsed']:
      mode = elapsed_data['mode']
      elapsed = elapsed_data['time']
      if mode == current_mode and current_inclusive:
        elapsed -= summary['current_elapsed']
      self._log[mode] = elapsed
    self._write_file(self._log, self.log_path)

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

  def __init__(self, user=None, modes=MODES, hidden=HIDDEN, abbrev=True):
    super().__init__(modes=modes, hidden=hidden, abbrev=abbrev)
    self.user = user

  def clear(self, new_description=''):
    # Create a new Era
    new_era = Era(user=self.user, current=True, description=new_description)
    # Get the current Era, if any, and mark it as not the current one.
    try:
      old_era = Era.objects.get(user=self.user, current=True)
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

  def switch_era(self, new_era=None, id=None):
    # Get the new era, make it the current one.
    if new_era is None:
      try:
        new_era = Era.objects.get(pk=id)
      except Era.DoesNotExist:
        return False
    else:
      assert new_era is not None
    new_era.current = True
    # Get the old era, make it not current anymore.
    try:
      old_era = Era.objects.get(user=self.user, current=True)
      old_era.current = False
    except Era.DoesNotExist:
      old_era = None
    # Commit changes.
    with transaction.atomic():
      if old_era is not None:
        old_era.save()
      new_era.save()
    return True

  def get_status(self, era=None):
    # Get the current Era, if not already given.
    if era is None:
      try:
        era = Era.objects.get(user=self.user, current=True)
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

  def switch_mode(self, mode, era=None):
    # Note: If mode is None, this will just create a new Period where the mode is None.
    self.validate_mode(mode)
    # Get the current Era, or create one if it doesn't exist.
    if era is None:
      era, created = Era.objects.get_or_create(user=self.user, current=True)
    # Create a new Period.
    now = int(time.time())
    new_period = Period(era=era, mode=mode, start=now)
    # Get the old Period, if any.
    try:
      old_period = Period.objects.get(era=era, end=None, next=None)
    except Period.DoesNotExist:
      old_period = None
    if old_period:
      if old_period.mode == mode:
        return old_period.mode, None
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
      era = Era.objects.get(user=self.user, current=True)
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

  def add_elapsed(self, mode, delta, era=None):
    assert mode is not None, mode
    self.validate_mode(mode)
    # Get the current Era or create it if it doesn't exist.
    if era is None:
      era, created = Era.objects.get_or_create(user=self.user, current=True)
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
      era = Era.objects.get(user=self.user, current=True)
    except Era.DoesNotExist:
      return {}
    data = {}
    for total in Total.objects.filter(era=era):
      data[total.mode] = total.elapsed
    return data

  #TODO: Remove.
  #      The parent class takes care of the basic interface, which is all get_summary() should be.
  #      Instead, let the view call special methods for all the display-related stuff.
  def get_summary(self, numbers='values', modes=RATIO_MODES, timespans=(6*60*60,)):
    summary = super().get_summary(numbers=numbers, modes=modes)
    #TODO: Remove this deletion once we've gotten rid of get_summary().
    if 'ratio_str' in summary:
      del summary['ratio_str']
    try:
      era = Era.objects.get(user=self.user, current=True)
      summary['era'] = era.description
    except Era.DoesNotExist:
      era = None
      summary['era'] = None
    summary['eras'] = []
    for other_era in Era.objects.filter(user=self.user, current=False):
      era_dict = {'id':other_era.id}
      if other_era.description:
        era_dict['name'] = other_era.description[:22]
      else:
        era_dict['name'] = str(other_era.id)
      summary['eras'].append(era_dict)
    summary['eras'].sort(key=lambda era_dict: era_dict['name'])
    if timespans:
      ratios = self._get_recent_ratios(timespans, numbers, modes, era=era)
      #TODO: Make 'ratios' a dict with keys 'num', 'denom', and 'timespans', which is the regular list.
      summary['ratios'].extend(ratios)
      summary['ratio_meta'] = {}
      summary['ratio_meta']['num'] = get_mode_name(RATIO_MODES[0], self.abbrev)
      summary['ratio_meta']['denom'] = get_mode_name(RATIO_MODES[1], self.abbrev)
      timespan = list(sorted(timespans))[0]
      summary['history'] = {}
      summary['history']['periods'] = self._get_recent_bars(timespan, numbers=numbers, era=era)
      summary['history']['adjustments'] = self._get_recent_adjustments(timespan, numbers=numbers,
                                                                       era=era)
      if numbers == 'values':
        summary['history']['timespan'] = timespan
      elif numbers == 'text':
        summary['history']['timespan'] = timestring(timespan, format='even', abbrev=False)
    summary['settings'] = self._get_user_settings()
    return summary

  def _get_user_settings(self):
    settings = {}
    for setting in User.SETTINGS:
      if self.user is None:
        try:
          settings[setting] = User.get_default(setting)
        except AttributeError:
          logging.warning('Could not get default value for setting {!r}.'.format(setting))
      else:
        settings[setting] = getattr(self.user, setting)
    return settings

  def _get_recent_ratios(self, timespans, numbers='values', modes=RATIO_MODES, era=None):
    """Get ratios for only the last `timespan`s seconds."""
    ratios = []
    if era is None:
      try:
        era = Era.objects.get(user=self.user, current=True)
      except Era.DoesNotExist:
        return ratios
    now = int(time.time())
    cutoffs = [now-timespan for timespan in timespans]
    min_cutoff = min(cutoffs)
    periods = Period.objects.filter(era=era, end__gte=min_cutoff).order_by('start')
    try:
      current_period = Period.objects.get(era=era, end=None, next=None)
    except Period.DoesNotExist:
      current_period = None
    totals = []
    for c in range(len(timespans)):
      totals.append(collections.defaultdict(int))
    for period in list(periods) + [current_period]:
      for c, cutoff in enumerate(cutoffs):
        if period and (period.end is None or period.end >= cutoff):
          if period.start >= cutoff:
            totals[c][period.mode] += period.elapsed
          else:
            totals[c][period.mode] += period.elapsed - (cutoff-period.start)
    #TODO: If an adjustment happened earlier than this cutoff, but during a period that ended after
    #      it, that might cause unnatural-feeling results. E.g. Maybe I left it on 'w' for an hour,
    #      but took a 30 min break and forgot to turn it off. So I did an adjustment of -30, but
    #      then left it on 'w' because I was back. This could possibly make a really weird ratio.
    for adjustment in Adjustment.objects.filter(era=era, timestamp__gte=min_cutoff):
      for c, cutoff in enumerate(cutoffs):
        if adjustment.timestamp >= cutoff:
          # Expand the adjustment backward into a "virtual period" `delta` long, ending when
          # the adjustment was made. Then, only count the part of this "virtual period" that's
          # after the cutoff.
          time_btwn_adj_and_cutoff = adjustment.timestamp - cutoff
          if abs(adjustment.delta) > time_btwn_adj_and_cutoff:
            sign = int(adjustment.delta / abs(adjustment.delta))
            totals[c][adjustment.mode] += sign * time_btwn_adj_and_cutoff
          else:
            totals[c][adjustment.mode] += adjustment.delta
    # Make sure there are no negative totals.
    for timespan_totals in totals:
      for mode in timespan_totals.keys():
        if timespan_totals[mode] < 0:
          timespan_totals[mode] = 0
    # Calculate the ratios.
    for c, timespan in enumerate(timespans):
      ratio = {'totals':totals[c]}
      mode0 = modes[0]
      mode1 = modes[1]
      logging.info('Totals for last {}s: {} in {}, {} in {}.'
                   .format(timespan, totals[c][mode0], mode0, totals[c][mode1], mode1))
      # Store the value of the ratio.
      if totals[c][mode1] == 0:
        if numbers == 'values':
          ratio['value'] = float('inf')
        elif numbers == 'text':
          ratio['value'] = '∞'
      else:
        ratio['value'] = totals[c][mode0]/totals[c][mode1]
        if numbers == 'text':
          ratio['value'] = '{:0.2f}'.format(ratio['value'])
      # Store the period of time the recent ratio is for.
      if numbers == 'values':
        ratio['timespan'] = timespan
      elif numbers == 'text':
        ratio['timespan'] = timestring(timespan, format='even', abbrev=True)
      ratios.append(ratio)
    return ratios

  def _get_recent_bars(self, timespan, numbers='values', era=None, total_width=99):
    """Get data for a display of recent periods."""
    bar_periods = []
    # Get current Era.
    if era is None:
      try:
        era = Era.objects.get(user=self.user, current=True)
      except Era.DoesNotExist:
        return bar_periods
    # Get a list of periods in the last `timespan` seconds.
    now = int(time.time())
    cutoff = now - timespan
    periods = Period.objects.filter(era=era, end__gte=cutoff).order_by('start')
    n_periods = len(periods)
    try:
      current_period = Period.objects.get(era=era, end=None, next=None)
      n_periods += 1
    except Period.DoesNotExist:
      current_period = None
    logging.info('Found {} periods in last {}.'.format(n_periods, timespan))
    # Create a list of bars from the periods.
    last_end = None
    for period in list(periods) + [current_period]:
      if period is None:
        continue
      # If we detect a gap between this period and the last one, insert an empty one.
      if last_end and period.start - last_end > 1:
        elapsed = period.start - last_end
        width = round(total_width * elapsed / timespan, 1)
        bar_periods.append({'mode':None, 'width':width, 'start':last_end, 'end':period.start,
                            'timespan':format_timespan(elapsed, numbers), 'mode_name':'None'})
        last_end = period.start
      if period.start < cutoff:
        if period.end is None:
          elapsed = timespan
        else:
          elapsed = period.end - cutoff
      else:
        elapsed = period.elapsed
      if period.end is None:
        end = now
      else:
        end = period.end
      last_end = end
      width = round(total_width * elapsed / timespan, 1)
      bar_periods.append({'mode':period.mode, 'width':width, 'start':period.start, 'end':end,
                          'timespan':format_timespan(period.elapsed, numbers),
                          'mode_name':get_mode_name(period.mode, self.abbrev)})
      logging.info('Found {} {} sec long ({}%): {} to {}'
                   .format(period.mode, period.elapsed, width, period.start, period.end))
    # Fill in empty gaps at start or end of timespan with empty bars.
    if len(bar_periods) == 0:
      bar_periods.append({'mode':None, 'width':total_width, 'start':cutoff, 'end':now,
                          'timespan':format_timespan(timespan, numbers), 'mode_name':'None'})
    else:
      if bar_periods[0]['start'] > cutoff+10:
        elapsed = bar_periods[0]['start'] - cutoff
        width = round(total_width * elapsed / timespan, 1)
        bar_periods.insert(0, {'mode':None, 'width':width, 'end':bar_periods[0]['start'], 'start':cutoff,
                               'timespan':format_timespan(elapsed, numbers), 'mode_name':'None'})
      if bar_periods[-1]['end'] < now-10:
        elapsed = now - bar_periods[-1]['end']
        width = round(total_width * elapsed / timespan, 1)
        bar_periods.append({'mode':None, 'width':width, 'start':bar_periods[-1]['end'], 'end':now,
                            'timespan':format_timespan(elapsed, numbers), 'mode_name':'None'})
    # Some post-processing to drop periods that are too small and make sure it all adds up to
    # total_width.
    bar_periods = [p for p in bar_periods if p['width'] >= 0.3]
    total_width = sum([p['width'] for p in bar_periods])
    if total_width != total_width:
      diff = min(0.3, total_width - total_width)
      bar_periods[-1]['width'] = round(bar_periods[-1]['width']+diff, 1)
    return bar_periods

  def _get_recent_adjustments(self, timespan, numbers='values', era=None, total_width=99):
    """Get data for a display of recent adjustments."""
    adjustments_data = []
    # Get current Era.
    if era is None:
      try:
        era = Era.objects.get(user=self.user, current=True)
      except Era.DoesNotExist:
        return adjustments_data
    # Get a list of adjustments in the last `timespan` seconds.
    now = int(time.time())
    cutoff = now - timespan
    adjustments = Adjustment.objects.filter(era=era, timestamp__gte=cutoff).order_by('timestamp')
    logging.info('Found {} adjustments in last {}.'.format(len(adjustments), timespan))
    for adjustment in adjustments:
      if adjustment.delta >= 0:
        sign = '+'
      else:
        sign = '-'
      x = round(total_width * (adjustment.timestamp-cutoff) / timespan, 1)
      magnitude = format_timespan(abs(adjustment.delta), numbers, label_smallest=False)
      adjustments_data.append({'mode':adjustment.mode, 'sign':sign, 'magnitude':magnitude, 'x':x,
                               'mode_name':get_mode_name(adjustment.mode, self.abbrev),
                               'timespan':format_timespan(abs(adjustment.delta), numbers)})
    return adjustments_data


class WorkTimesWeb(WorkTimes):

  def __init__(self, modes=MODES, hidden=HIDDEN, abbrev=True, api_endpoint=API_ENDPOINT,
               timeout=TIMEOUT, verify=True, cookie=None, status_path=None, log_path=None,
               summary_path=None):
    super().__init__(modes=modes, hidden=hidden, abbrev=abbrev)
    #TODO: Actually support abbrev.
    self.api_endpoint = api_endpoint
    self.timeout = timeout
    self.verify = verify
    self.cookie = cookie
    if isinstance(summary_path, pathlib.Path) or summary_path is None:
      self.summary_path = summary_path
    else:
      self.summary_path = pathlib.Path(summary_path)
    if status_path and log_path:
      self.work_times_files = WorkTimesFiles(modes=self.modes, hidden=self.hidden, abbrev=self.abbrev,
                                             status_path=status_path, log_path=log_path)
    else:
      self.work_times_files = None
    # Cache of current status.
    self._summary = None

  #TODO: Finish implementing rest of the methods.

  def clear(self):
    #TODO: Support --sync.
    self._summary = None
    self._make_request('/clear', method='post', timeout=self.timeout)

  def switch_mode(self, new_mode):
    # Override this method from the parent, since it's a special case with web.
    self.validate_mode(new_mode)
    # Get the old status.
    old_mode, old_elapsed = self.get_status()
    if old_mode == new_mode:
      return old_mode, None
    # Make the switch.
    params = {'mode':new_mode}
    if self.work_times_files:
      self.work_times_files.set_status(new_mode)
      #TODO: Sync worklog.txt too.
    # Invalidate the cache right before the change.
    self._summary = None
    self._make_request('/switch', method='post', data=params, timeout=self.timeout)
    return old_mode, old_elapsed

  def add_elapsed(self, mode, delta):
    # Override this method in the parent, since it's a special case with web.
    #TODO: Support --sync.
    self.validate_mode(mode)
    self._summary = None
    params = {'mode':mode}
    if delta < 0:
      params['subtract'] = abs(delta)//60
    else:
      params['add'] = delta//60
    self._make_request('/adjust', method='post', data=params, timeout=self.timeout)

  def get_summary(self, numbers='values'):
    # Override this method in the parent, since it's a special case with web.
    if self._summary is None:
      self._summary = self._make_request('?format=json&numbers={}'.format(numbers),
                                         format='json', timeout=self.timeout)
    if self.work_times_files:
      self.work_times_files.write_summary(self._summary, current_inclusive=True)
    if self.summary_path:
      with self.summary_path.open(mode='w') as summary_file:
        summary_file.write(json.dumps(self._summary))
    return self._summary

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
    if self.cookie:
      kwargs['cookies'] = {COOKIE_NAME:self.cookie}
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
