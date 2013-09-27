#!/usr/bin/python
"""
Interface:
worklog.txt
- The order of the lines is not guaranteed, so that it can be written straight
  from a dict.
- It is not required to contain all modes, even if zero. Instead of adding in
  missing modes there, I will only do it on output to the user.
  - This makes it more extensible (easier to add new modes)
  - Also applies to the 's' mode special consideration (just don't print that
    one)
"""
import os
import sys
import time

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


# seems to be working
def switch_mode(mode):
  """Mark the time spent in the last mode and mark this new one"""
  sys.stderr.write("Oops, this script doesn't do the logging yet!\n")
  checkfiles(log_file, status_file)

  if mode not in MODES:
    fail("Error: Unrecognized mode "+mode)

  now = int(time.time())
  times = readlog(log_file)
  status = readlog(status_file)
  if len(status) != 1:
    fail("Error: Status file "+status_file+" should have 1 entry. Currently "+
      "has "+str(len(status)))
  old_mode = status.keys()[0]
  elapsed = now - status[old_mode]

  times[old_mode] = elapsed + times.get(old_mode, 0)
  status = {mode:now}
  #TODO: also print new times to notify-send

  writelog(log_file, times)
  writelog(status_file, status)


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
  """Clears the log"""
  sys.stdout.write("Oops, this script can't do 'clear' yet!\n")
  # don't print 0's. just blank it, and the 0's will be inferred when needed
  writelog(log_file, {})
  writelog(status_file, {}) # not certain about this one yet
  #TODO: print a message to notify-send


# seems to be working
def adjust(adjustments):
  """Change the accumulated times in the work log. Syntax: p+30 w-20"""

  times = readlog(log_file)

  for adjustment in adjustments:

    try:
      index = adjustment.index("+")
    except ValueError, e:
      try:
        index = adjustment.index("-")
      except ValueError, e:
        fail("Error: adjustment syntax incorrect in "+adjustment)

    mode = adjustment[:index]
    try:
      amount = int(adjustment[index:])
    except ValueError, e:
      fail("Error: adjustment syntax incorrect in "+adjustment)
    if mode not in MODES:
      fail("Error: invalid mode given in adjustment command "+adjustment)

    times[mode] = times.get(mode, 0) + 60 * amount

  writelog(log_file, times)


##### Basic I/O #####

def checkfiles(log_file, status_file):
  """Make sure the two files exist"""


def readlog(log_file):
  """Read log file into a dict (works for status file too)"""
  times = {}
  with open(log_file, 'r') as lines:
    for line in lines:
      (mode, seconds) = line.rstrip("\r\n").split("\t")
      times[mode] = int(seconds)
  return times


"""DEBUG VERSION"""
def writelog(log_file, times):
  """Replace existing log file with new version (works for status file too)"""
  # with open(log_file, 'w') as log_fh:
  for mode in times:
    sys.stdout.write(mode+"\t"+str(times.get(mode, 0))+"\n")
      # log_fh.write(mode+"\t"+str(times.get(mode, 0))+"\n")

def writelog_real(log_file, times):
  """Replace existing log file with new version (works for status file too)"""
  with open(log_file, 'w') as log_fh:
    for mode in times:
      log_fh.write(mode+"\t"+str(times.get(mode, 0))+"\n")


def print_status():
  times = readlog(log_file)
  for mode in times:
    print mode+"\t"+str(times[mode])

def print_status_real():
  times = readlog(log_file)
  for mode in times:
    #TODO: print to notify-send
    # don't show 's' time
    print mode+"\t"+str(times[mode])


def fail(message):
  """Quick way of writing the below two lines"""
  sys.stderr.write(message+"\n")
  sys.exit(1)


##### Basic stuff #####



if __name__ == "__main__":
  main()