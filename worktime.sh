#!/bin/bash
# Original script
# Rewrote it in Python once this got too unwieldy
set -ue

WORK='w'
PLAY='p'
NEUT='n'
STOP='s'
CMND='0'
CLEAR_CMND='clear'
STATUS_CMND='status'
ADJUST_CMND='adjust'
STATUS_FILE="$HOME/.local/share/nbsdata/workstatus.txt"
LOG_FILE="$HOME/.local/share/nbsdata/worklog.txt"
LOG_TEMP="$HOME/.local/share/nbsdata/worktemp.txt"
NOTIFY_TEMP="$HOME/.local/share/nbsdata/notifytemp.txt"

if [[ ! "$@" ]]; then
  echo "USAGE:
  $ $0 [type]
Where [type] is:
$WORK    work
$PLAY    play
$NEUT    neutral
$STOP    stop"
  exit
else
  type="$1"
  if [ ${#type} -gt 1 ]; then
    echo "Error: first argument not a recognized type" 1>&2
    exit 1
  fi
fi

# convert seconds to minutes and hours
to_time () {
  sec_total="$1"
  min=$(echo "$sec_total/60" | bc)
  sec=$((sec_total - (min * 60)))
  if [ $min -lt 60 ]; then
    echo "$min"
  else
    min_total=$min
    hr=$(echo "$min_total/60" | bc)
    min=$((min_total - (hr * 60)))
    if [ $min -lt 10 ]; then min='0'$min; fi
    echo "$hr:$min"
  fi
}

# If first argument is $CMND, execute special command
if [ "$type" == "$CMND" ]; then
  if [ $# -lt 2 ]; then
    echo "Error: must provide a command argument after $CMND" 1>&2
    exit 1
  fi
  command="$2"

  # reset times log
  if [ "$command" == "$CLEAR_CMND" ]; then
    if [ -f "$LOG_FILE" ]; then rm "$LOG_FILE"; fi
    echo -ne "$STOP\t"$(date +%s) > "$STATUS_FILE"
    notify-send "log cleared"
  fi

  # display status without changing state
  if [ "$command" == "$STATUS_CMND" ]; then
    if [[ -f "$STATUS_FILE" && -f "$LOG_FILE" ]]; then
      now=$(date +%s)
      oldtype=$(cut -f 1 "$STATUS_FILE")
      oldtime=$(cut -f 2 "$STATUS_FILE")
      elapsed=$((now-oldtime))
      elapsed_time=$(to_time $elapsed)
      echo -n > "$NOTIFY_TEMP"
      cat "$LOG_FILE" | while read line; do
        logtype=$(echo "$line" | cut -f 1)
        logtime=$(echo "$line" | cut -f 2)
        echo -n "$logtype\t"$(to_time $logtime)"\n" >> "$NOTIFY_TEMP"
      done
      notify_string=$(cat "$NOTIFY_TEMP")
      notify-send "Status:  $oldtype     $elapsed_time" \
        "$(echo -ne "$notify_string")"
    else
      notify-send "Error" "Not started or missing files"
    fi
  fi

  if [ "$command" == "$ADJUST_CMND" ]; then
    for arg in $@; do
      if [[ "$arg" == "$CMND" || "$arg" == "$ADJUST_CMND" ]]; then continue; fi
      adj_type=${arg:0:1}
      adj_op=${arg:1:1}
      adj_amt=${arg:2}
    done
  fi

  exit
fi


# Get elapsed time since last invocation
# from $STATUS_FILE
now=$(date +%s)
if [ -f "$STATUS_FILE" ]; then
  oldtype=$(cut -f 1 "$STATUS_FILE")
  oldtime=$(cut -f 2 "$STATUS_FILE")

  elapsed=$((now-oldtime))
  to_time $elapsed
fi
# Replace $STATUS_FILE
echo -ne "$type\t$now" > "$STATUS_FILE"


# Read $LOG_FILE, update totals, write new file, send notification to screen
work_time=0
play_time=0
neut_time=0
if [ -f "$LOG_FILE" ]; then
  cat "$LOG_FILE" | while read line; do
    logtype=$(echo "$line" | cut -f 1)
    logtime=$(echo "$line" | cut -f 2)
    if [ "$logtype" == "$oldtype" ]; then
      logtime=$((logtime + elapsed))
      echo "adjusted logtime to $logtime"
    fi

    if [ "$logtype" == "$WORK" ]; then
      work_time=$logtime
      echo -e "$WORK\t$work_time" > "$LOG_TEMP"
      echo -n "$WORK\t"$(to_time $work_time)"\n" > "$NOTIFY_TEMP"
    fi
    if [ "$logtype" == "$PLAY" ]; then
      play_time=$logtime
      echo -e "$PLAY\t$play_time" >> "$LOG_TEMP"
      echo -n "$PLAY\t"$(to_time $play_time)"\n" >> "$NOTIFY_TEMP"
    fi
    if [ "$logtype" == "$NEUT" ]; then
      neut_time=$logtime
      echo -e "$NEUT\t$neut_time" >> "$LOG_TEMP"
      echo -n "$NEUT\t"$(to_time $neut_time)"\n" >> "$NOTIFY_TEMP"
    fi
  done
else
  echo -e "$WORK\t0\n$PLAY\t0\n$NEUT\t0" > "$LOG_TEMP"
  echo -e "$WORK\t0\n$PLAY\t0\n$NEUT\t0" > "$NOTIFY_TEMP"
fi

mv "$LOG_TEMP" "$LOG_FILE"
notify_string=$(cat "$NOTIFY_TEMP")
notify-send "$type" "$(echo -ne "$notify_string")"