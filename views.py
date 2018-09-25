import json
import logging
import time
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, reverse
from django.views.decorators.csrf import csrf_exempt
from .models import Era, Period
from .worktime import WorkTimesDatabase, timestring
from utils import QueryParams, boolish
log = logging.getLogger(__name__)
HISTORY_BAR_TIMESPAN = 2*60*60


##### Views #####

def main(request):
  params = QueryParams()
  params.add('format', choices=('html', 'plain', 'json'), default='html')
  params.add('numbers', choices=('values', 'text'), default='text')
  params.parse(request.GET)
  work_times = WorkTimesDatabase()
  summary = work_times.get_summary(numbers=params['numbers'], timespans=(12*60*60, 2*60*60))
  summary['modes'] = work_times.modes
  summary['eras'] = []
  current_era = None
  for era in Era.objects.filter(current=False):
    era_dict = {'id':era.id}
    if era.description:
      era_dict['name'] = era.description[:22]
    else:
      era_dict['name'] = era.id
    if era.current:
      current_era = era
    summary['eras'].append(era_dict)
  if params['format'] == 'html':
    summary['history'] = {}
    summary['history']['timespan'] = timestring(HISTORY_BAR_TIMESPAN, format='even', abbrev=False)
    summary['history']['periods'] = get_bar_periods(HISTORY_BAR_TIMESPAN, era=current_era)
    return render(request, 'worktime/main.tmpl', summary)
  elif params['format'] == 'json':
    return HttpResponse(json.dumps(summary), content_type='application/json')
  elif params['format'] == 'plain':
    lines = []
    lines.append('status\t{current_mode}\t{current_elapsed}'.format(**summary))
    for elapsed in summary['elapsed']:
      lines.append('total\t{mode}\t{time}'.format(**elapsed))
    for ratio in summary['ratios']:
      lines.append('ratio\t{0}\t{timespan}\t{value}'.format(summary['ratio_str'], **ratio))
    return HttpResponse('\n'.join(lines), content_type=settings.PLAINTEXT)

@csrf_exempt
def switch(request):
  if request.method != 'POST':
    log.warning('Wrong method.')
    return HttpResponseRedirect(reverse('worktime_main'))
  work_times = WorkTimesDatabase()
  params = QueryParams()
  params.add('mode', choices=work_times.modes)
  params.parse(request.POST)
  if params.invalid_value:
    log.warning('Invalid or missing mode {!r}.'.format(params.get('mode')))
    return HttpResponseRedirect(reverse('worktime_main'))
  old_mode, old_elapsed = work_times.switch_mode(params['mode'])
  return HttpResponseRedirect(reverse('worktime_main'))

@csrf_exempt
def adjust(request):
  if request.method != 'POST':
    log.warning('Wrong method.')
    return HttpResponseRedirect(reverse('worktime_main'))
  work_times = WorkTimesDatabase()
  params = QueryParams()
  params.add('mode', choices=work_times.modes)
  params.add('add', type=int)
  params.add('subtract', type=int)
  params.parse(request.POST)
  if (not params['mode']
      or (params['add'] is None and params['subtract'] is None)
      or (params['add'] is not None and params['add'] < 0)
      or (params['subtract'] is not None and params['subtract'] < 0)
  ):
    log.warning('Invalid mode ({mode!r}), add ({add!r}), or subtract ({subtract!r}).'.format(**params))
    return HttpResponseRedirect(reverse('worktime_main'))
  if params['add'] is not None:
    delta = params['add']
  elif params['subtract'] is not None:
    delta = -params['subtract']
  log.info('Adding {!r} to {!r}'.format(delta, params['mode']))
  work_times.add_elapsed(params['mode'], delta*60)
  return HttpResponseRedirect(reverse('worktime_main'))

def switchera(request):
  if request.method != 'POST':
    log.warning('Wrong method.')
    return HttpResponseRedirect(reverse('worktime_main'))
  params = QueryParams()
  params.add('era', type=int)
  params.add('newEra')
  params.parse(request.POST)
  work_times = WorkTimesDatabase()
  if params['newEra']:
    work_times.clear(params['newEra'])
  elif params['era'] is not None:
    work_times.switch_era(params['era'])
  return HttpResponseRedirect(reverse('worktime_main'))

@csrf_exempt
def clear(request):
  if request.method != 'POST':
    log.warning('Wrong method.')
    return HttpResponseRedirect(reverse('worktime_main'))
  work_times = WorkTimesDatabase()
  work_times.clear()
  return HttpResponseRedirect(reverse('worktime_main'))


def get_bar_periods(timespan, era=None):
  bar_periods = []
  if era is None:
    try:
      era = Era.objects.get(current=True)
    except Era.DoesNotExist:
      return bar_periods
  now = int(time.time())
  cutoff = now - timespan
  periods = Period.objects.filter(era=era, end__gte=cutoff).order_by('start')
  n_periods = len(periods)
  try:
    current_period = Period.objects.get(era=era, end=None, next=None)
    n_periods += 1
  except Period.DoesNotExist:
    current_period = None
  log.info('Found {} periods in last {}.'.format(n_periods, timespan))
  for period in list(periods) + [current_period]:
    if period is None:
      continue
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
    width = round(100 * elapsed / timespan)
    bar_periods.append({'mode':period.mode, 'width':width, 'start':period.start, 'end':end})
    log.info('Found {} {} sec long ({}px): {} to {}'
             .format(period.mode, period.elapsed, width, period.start, period.end))
  # Add in empty bar at end if last period doesn't extend up to current time.
  if len(bar_periods) == 0:
    bar_periods.append({'mode':None, 'width':100, 'end':now})
  else:
    if bar_periods[0]['start'] > cutoff+10:
      width = round(100 * (bar_periods[0]['start'] - cutoff) / timespan)
      bar_periods.insert(0, {'mode':None, 'width':width, 'start':cutoff, 'end':bar_periods[0]['start']})
    if bar_periods[-1]['end'] < now-10:
      width = round(100 * (now - bar_periods[-1]['end']) / timespan)
      bar_periods.append({'mode':None, 'width':width, 'start':bar_periods[-1]['end'], 'end':now})
  return bar_periods
