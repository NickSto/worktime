#!/usr/bin/python
import os, sys

MODES = ['w','p','n','s']
LOG_FILE_REL    = '.mymisc/worklog.txt'
STATUS_FILE_REL = '.mymisc/workstatus.txt'
CMD_CLEAR  = 'clear'
CMD_ADJUST = 'adjust'
CMD_STATUS = 'status'

log_file    = os.path.expanduser('~')+os.sep+LOG_FILE_REL
status_file = os.path.expanduser('~')+os.sep+STATUS_FILE_REL

def main():

  if len(sys.argv) == 1 or '-h' in sys.argv[1][0:3]:
    script_name = os.path.basename(sys.argv[0])
    print """USAGE:
  $ """+script_name+""" [mode]
or
  $ """+script_name+""" [command] [arguments]
Where [mode] is a single letter (one of """+', '.join(MODES)+""")
and [command] is one of the following:
  clear:
Clears the log; restarts at 0 for all modes.
  adjust:
Add or subtract times from the recorded log."""
    sys.exit(0)
  else:
    arg1 = sys.argv[1]
    if arg1 in MODES:
      switch_mode(arg1)
    else:
      run_command(arg1, sys.argv[2:])


def switch_mode(mode):
  """Mark the time spent in the last mode and mark this new one"""
  fail("Oops, this script doesn't do the logging yet!")
  checkfiles(log_file, status_file)


def run_command(command, args):
  """Execute a special command"""
  checkfiles(log_file, status_file)

  if command == CMD_CLEAR:
    clear()
  elif command == CMD_ADJUST:
    adjust(args)
  elif command == CMD_STATUS:
    print_status()
  else:
    fail('Error: Command "'+command+'" not recognized!')


def clear():
  """Clears the log, resetting all times to 0"""
  fail("Oops, this script can't do 'clear' yet!")


def print_status():
  times = readlog(log_file)
  for mode in times:
    # TODO: print to notify-send
    print mode+"\t"+str(times[mode])


def adjust(adjustments):
  """Change the accumulated times in the work log"""
  
  times = readlog(log_file)

  for adjustment in adjustments:
    if len(adjustment) < 3:
      fail("Error: adjustment syntax incorrect in "+adjustment)
    mode = adjustment[0:1]
    try:
      amount = int(adjustment[1:])
    except ValueError, e:
      fail("Error: adjustment syntax incorrect in "+adjustment)
    if mode not in MODES:
      fail("Error: invalid mode given in adjustment command "+adjustment)

    times[mode] = times.get(mode, 0) + 60 *amount

  writelog(log_file, times)


def checkfiles(log_file, status_file):
  """Make sure the two files exist"""


def readlog(log_file):
  """Read log file into a dict"""
  times = {}
  with open(log_file, 'r') as lines:
    for line in lines:
      (mode, seconds) = line.rstrip("\r\n").split("\t")
      times[mode] = int(seconds)
  return times


def writelog(log_file, times):
  """Replace existing log file with new version"""
  with open(log_file, 'w') as log_fh:
    for mode in times:
      log_fh.write(mode+"\t"+str(times.get(mode, 0))+"\n")


def fail(message):
  """Quick way of writing the below two lines"""
  sys.stderr.write(message+"\n")
  sys.exit(1)


if __name__ == "__main__":
  main()