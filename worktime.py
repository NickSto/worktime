#!/usr/bin/env python
"""
Requires pynotify (python-notify package in Ubuntu)
Interface:
~/.local/share/nbsdata/workstatus.txt
~/.local/share/nbsdata/worklog.txt
- The order of the lines is not guaranteed, so that it can be written straight
  from a dict.
- It is not required to contain all modes, even if zero. Instead of adding in
  missing modes there, I will only do it on output to the user.
  - This makes it more extensible (easier to add new modes)
  - Also applies to the 's' mode special consideration (just don't print that
    one)
"""
from __future__ import division
import os
import re
import sys
import time
import pynotify

MODES = ['w','p','n','s']
HIDDEN = ['s']
DATA_DIR    = '.local/share/nbsdata'
LOG_FILE    = 'worklog.txt'
STATUS_FILE = 'workstatus.txt'
CMD_CLEAR   = 'clear'
CMD_ADJUST  = 'adjust'
CMD_STATUS  = 'status'

home_dir    = os.path.expanduser('~')
log_file    = os.path.join(home_dir, DATA_DIR, LOG_FILE)
status_file = os.path.join(home_dir, DATA_DIR, STATUS_FILE)


def main():

  if len(sys.argv) == 1 or '-h' in sys.argv[1][0:3]:
    script_name = os.path.basename(sys.argv[0])
    print """USAGE:
  $ """+script_name+""" [mode]
or
  $ """+script_name+""" [command] [arguments]
Where [mode] is a single letter (one of """+', '.join(MODES)+""")
And [command] is one of the following:
  clear:  Clears the log; restarts at 0 for all modes.
  adjust: Add or subtract minutes from the recorded log.
          Format: "p+20 w-5 n+100"
  status: Show the current times.
Keeps track of the current status (mode and start time) in:
"""+status_file+"""
Keeps track of cumulative totals (in seconds) in:
"""+log_file
    sys.exit(0)
  else:
    arg1 = sys.argv[1]
    if arg1 in MODES:
      switch_mode(arg1)
    else:
      run_command(arg1, sys.argv[2:])


def switch_mode(mode):
  """Mark the time spent in the last mode and mark this new one"""

  if mode not in MODES:
    fail("Error: Unrecognized mode "+mode)

  now = int(time.time())
  times = readlog(log_file)
  status = readlog(status_file)
  if len(status) > 1:
    fail("Error: Status file "+status_file+" should have 1 entry. Currently "+
      "has "+str(len(status)))
  elif len(status) < 1:
    status = {mode:now}

  old_mode = status.keys()[0]
  elapsed = now - status[old_mode]

  times[old_mode] = elapsed + times.get(old_mode, 0)
  status = {mode:now}
  message = mode+"\t( added  "+old_mode+"  "+str(timestring(elapsed))+" )"

  writelog(log_file, times)
  writelog(status_file, status)

  print_times(message)


def run_command(command, args):
  """Execute a special command"""

  if command == CMD_CLEAR:
    clear()
  elif command == CMD_ADJUST:
    adjust(args)
  elif command == CMD_STATUS:
    print_times(status_str())
  elif re.match(r'^\w+[+-]\d+$', command):  # 1st argument = adjustment command
    adjust([command] + args)
  else:
    fail('Error: Command "'+command+'" not recognized!')


def clear():
  """Clears the log"""
  # don't print 0's. just blank it, and the 0's will be inferred when needed
  writelog(log_file, {})
  writelog(status_file, {})
  notify("Log cleared", "")


def adjust(adjustments):
  """Change the accumulated times in the work log. Syntax: p+30 w-20"""

  times = readlog(log_file)
  report = ""

  for adj in adjustments:

    if '+' in adj:
      index = adj.index("+")
    elif '-' in adj:
      index = adj.index("-")
    else:
      fail("Error: adjustment syntax incorrect in "+adj)

    mode = adj[:index]
    try:
      amount = int(adj[index:])
    except ValueError:
      fail("Error: adjustment syntax incorrect in "+adj)
    if mode not in MODES:
      fail("Error: invalid mode given in adjustment command "+adj)

    times[mode] = times.get(mode, 0) + 60 * amount
    if times[mode] < 0:
      times[mode] = 0

    report += "\t"+mode+" "+adj[index]+" "+timestring(abs(amount*60))

  writelog(log_file, times)

  print_times(report)


##### Basic I/O #####


def readlog(log_file):
  """Read log file into a dict (works for status file too)"""
  times = {}
  if not os.path.exists(log_file):
    return times
  with open(log_file, 'r') as lines:
    for line in lines:
      (mode, seconds) = line.rstrip("\r\n").split("\t")
      times[mode] = int(seconds)
  return times


def writelog_debug(log_file, times):
  """Replace existing log file with new version (works for status file too)"""
  # with open(log_file, 'w') as log_fh:
  for mode in times:
    sys.stdout.write(mode+"\t"+str(times.get(mode, 0))+"\n")
      # log_fh.write(mode+"\t"+str(times.get(mode, 0))+"\n")

def writelog(log_file, times):
  """Replace existing log file with new version (works for status file too)"""
  with open(log_file, 'w') as log_fh:
    for mode in times:
      log_fh.write(mode+"\t"+str(times.get(mode, 0))+"\n")


def readstatus(status_file):
  status = readlog(status_file)
  if status:
    mode = status.keys()[0]
    elapsed = int(time.time()) - status[mode]
    return mode, elapsed
  else:
    return None, None


def status_str():
  """Read status file, convert into human-readable status string"""
  mode, elapsed = readstatus(status_file)
  if mode:
    return '{}\t{}'.format(mode, timestring(elapsed))
  else:
    return ''


def print_times(message="", ratio=('p','w')):
  """Print state summary to notification system"""
  title = ''
  body = ''
  if message:
    title = "Status:\t"+message
  current_mode, current_time = readstatus(status_file)
  times = readlog(log_file)
  for mode in times:
    if mode == current_mode:
      times[mode] += current_time
  # get union of builtin modes and ones in file (each mode only once)
  modes = list(set(times.keys()) | set(MODES))
  for mode in modes:
    if mode not in HIDDEN:
      body += '{}\t{}\n'.format(mode, timestring(times.get(mode, 0)))
  # If requested, calculate the ratio of the times for the specified modes.
  if ratio and times.get(ratio[0]) and times.get(ratio[1]):
    ratio_value = times[ratio[0]] / times[ratio[1]]
    body += '{}/{}:\t{:0.2f}'.format(ratio[0], ratio[1], ratio_value)
  if not title:
    title = ' '
  if not body:
    body = ' '
  notify(title, body)


def notify(title, body):
  pynotify.init("worktime")
  notice = pynotify.Notification(title, body)
  notice.show()


def timestring(sec_total):
  """Convert time in seconds to HH:MM:SS string"""
  min_total = sec_total // 60
  hrs = min_total // 60
  min = min_total % 60
  if hrs:
    return "%d:%02d" % (hrs, min)
  else:
    return str(min)

def fail(message):
  """Quick way of writing the below two lines"""
  sys.stderr.write(message+"\n")
  sys.exit(1)



if __name__ == "__main__":
  main()
