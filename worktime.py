#!/usr/bin/env python3
import argparse
import logging
import os
import pathlib
import sys
import time
assert sys.version_info.major >= 3, 'Python 3 required'

MODES = ['w','p','n','s']
HIDDEN = ['s']
DATA_DIR    = pathlib.Path('~/.local/share/nbsdata').expanduser()
LOG_PATH    = DATA_DIR / 'worklog.txt'
STATUS_PATH = DATA_DIR / 'workstatus.txt'

USAGE = """Usage:
  $ {0} [mode]
or
  $ {0} [command] [arguments]""".format(sys.argv[0])

HELP = """
[mode] is a single letter (one of {})
[command] is one of the following:
  clear:  Clears the log; restarts at 0 for all modes.
  adjust: Add or subtract minutes from the recorded log.
          Give any number of arguments in the format [mode][+-][minutes]
          E.g. "p+20", "w-5", "n+100"
  status: Show the current times.

Note: This requires the notify2 package.""".format(', '.join(MODES))


def main(argv):

  logging.basicConfig(stream=sys.stderr, format='%(message)s')

  if '-h' in sys.argv or '--help' in sys.argv or len(sys.argv) <= 1:
    print(USAGE, file=sys.stderr)
    print(HELP, file=sys.stderr)
    return 1

  work_times = WorkTimes(data_store='files', modes=MODES, hidden=HIDDEN,
                         log_path=LOG_PATH, status_path=STATUS_PATH)

  if sys.argv[1] in MODES:
    new_mode = sys.argv[1]
    old_mode, old_elapsed = work_times.switch_mode(new_mode)
    if old_mode is None or old_mode in HIDDEN or old_mode == new_mode:
      message = '(was {})'.format(old_mode)
    else:
      message = '(added {} to {})'.format(timestring(old_elapsed), old_mode)
      print('Setting message to {!r}'.format(message))
    title, body = make_report(work_times, message)
    feedback(title, body, stdout=True, notify=True)
  else:
    command = sys.argv[1]
    if command == 'clear':
      work_times.clear()
      feedback('Log cleared', stdout=True, notify=True)
    elif command == 'adjust':
      adjustments = sys.argv[2:]
      if len(adjustments) == 0:
        fail('Error: "adjust" command requires arguments.')
      adjust(work_times, adjustments)
    elif command == 'status':
      title, body = make_report(work_times)
      feedback(title, body, stdout=True, notify=True)
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
  feedback('Times adjusted', '\n'.join(messages), stdout=True, notify=True)


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


def make_report(work_times, message=None, ratio=('p', 'w')):
  # Get the current status and how long it's been happening.
  current_mode, elapsed = work_times.get_status()
  title = 'Status: {} '.format(current_mode)
  if message is None:
    if elapsed is not None:
      title += timestring(elapsed)
  else:
    title += message
  # Get all the elapsed times and add the time of the current mode to them.
  all_elapsed = work_times.get_all_elapsed()
  if current_mode:
    all_elapsed[current_mode] = elapsed + all_elapsed.get(current_mode, 0)
  # Format a list of all the current elapsed times.
  lines = []
  all_modes = MODES[:]
  for mode in all_elapsed.keys():
    if mode not in all_modes:
      all_modes.append(mode)
  for mode in all_modes:
    if mode in all_elapsed and mode not in HIDDEN:
      lines.append('{}:\t{}'.format(mode, timestring(all_elapsed[mode])))
  body = '\n'.join(lines)
  # If requested, calculate the ratio of the times for the specified modes.
  if ratio and ratio[0] in all_elapsed and ratio[1] in all_elapsed:
    ratio_value = all_elapsed[ratio[0]] / all_elapsed[ratio[1]]
    body += '\n{}/{}:\t{:0.2f}'.format(ratio[0], ratio[1], ratio_value)
  return title, body


def timestring(sec_total):
  """Convert time in seconds to HH:MM string"""
  min_total = sec_total // 60
  hours = min_total // 60
  minutes = min_total % 60
  if hours:
    return "%d:%02d" % (hours, minutes)
  else:
    return str(minutes)


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

  def __init__(self, data_store='files', modes=MODES, hidden=HIDDEN,
               log_path=LOG_PATH, status_path=STATUS_PATH):
    self.data_store = data_store
    self.modes = modes
    self.hidden = hidden
    self._log = None
    if isinstance(log_path, pathlib.Path):
      self.log_path = log_path
    else:
      log_path = pathlib.Path(log_path)
    if isinstance(status_path, pathlib.Path):
      self.status_path = status_path
    else:
      status_path = pathlib.Path(status_path)

  def clear(self):
    """Erase all history and the current status."""
    self.set_status()
    if self.data_store == 'files':
      self._clear_elapsed_files()
    elif self.data_store == 'database':
      self._clear_elapsed_database()

  def switch_mode(self, new_mode):
    old_mode, old_elapsed = self.get_status()
    if old_mode is not None and old_mode not in self.hidden:
      # Save the elapsed time we spent in the old mode.
      if old_mode == new_mode:
        return old_mode, None
      now = int(time.time())
      elapsed = self.get_elapsed(old_mode)
      elapsed = elapsed + old_elapsed
      self.set_elapsed(old_mode, elapsed)
    self.set_status(new_mode)
    return old_mode, old_elapsed

  def add_elapsed(self, mode, delta):
    elapsed = self.get_elapsed(mode)
    self.set_elapsed(mode, elapsed+delta)

  def get_status(self):
    """Return (mode, elapsed): the current mode string, and the number of seconds we've been in it."""
    if self.data_store == 'files':
      mode, start = self._get_raw_status_files()
    elif self.data_store == 'database':
      mode, start = self._get_raw_status_database()
    if mode is not None and mode not in self.modes:
      raise WorkTimeError('Current mode {!r} is not one of the valid modes {}.'
                          .format(mode, self.modes))
    if mode is None:
      return None, None
    else:
      now = int(time.time())
      return mode, now - start

  def set_status(self, mode=None):
    if mode is not None and mode not in self.modes:
      raise WorkTimeError('Cannot set mode {!r}: not one of valid modes {}'
                          .format(mode, self.modes))
    if self.data_store == 'files':
      self._set_status_files(mode)
    elif self.data_store == 'database':
      self._set_status_database(mode)

  def get_elapsed(self, mode):
    if mode not in self.modes:
      raise WorkTimeError('Cannot get elapsed for mode {!r}: not one of valid modes {}'
                          .format(mode, self.modes))
    if self.data_store == 'files':
      return self._get_elapsed_files(mode)
    elif self.data_store == 'database':
      return self._get_elapsed_database(mode)

  def set_elapsed(self, mode, elapsed):
    if mode not in self.modes:
      raise WorkTimeError('Cannot set elapsed for mode {!r}: not one of valid modes {}'
                          .format(mode, self.modes))
    if self.data_store == 'files':
      self._set_elapsed_files(mode, elapsed)
    elif self.data_store == 'database':
      self._set_elapsed_database(mode, elapsed)

  def get_all_elapsed(self):
    if self.data_store == 'files':
      if self._log is None:
        self._log = self._read_log()
      return self._log
    elif self.data_store == 'database':
      return self._get_all_elapsed_database()

  # Files interfaces.

  def _set_status_files(self, mode):
    data = {}
    if mode is not None:
      start = int(time.time())
      data[mode] = start
    self._write_file(data, self.status_path)

  def _get_raw_status_files(self):
    """Return (mode, start): The current mode string, and the timestamp of when it started
    (in seconds)."""
    data = self._read_file(self.status_path)
    if not data:
      return None, None
    else:
      if len(data.keys()) != 1:
        raise WorkTimeError('Status file {!r} contains {} statuses.'
                            .format(str(self.status_path), len(data.keys())))
      mode = list(data.keys())[0]
      start = data[mode]
      return mode, start

  def _get_elapsed_files(self, mode):
    """Read the log file and get the elapsed time for the given mode."""
    if self._log is None:
      self._log = self._read_log()
    return self._log.get(mode, 0)

  def _set_elapsed_files(self, mode, elapsed):
    if self._log is None:
      self._log = self._read_log()
    self._log[mode] = elapsed
    self._write_file(self._log, self.log_path)

  def _clear_elapsed_files(self):
    self._log = None
    self._write_file({}, self.log_path)

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


def writelog(log_file, times):
  """Replace existing log file with new version (works for status file too)"""
  with log_file.open(mode='w') as log_file:
    for mode in times:
      log_file.write('{}\t{}\n'.format(mode, times.get(mode, 0)))


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
