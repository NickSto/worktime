import json
import logging
import time
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, reverse
from django.views.decorators.csrf import csrf_exempt
from .models import Era, Period, AuthorizedCookie
from .worktime import WorkTimesDatabase, timestring
from utils import QueryParams, boolish
log = logging.getLogger(__name__)

HISTORY_BAR_TIMESPAN = 2*60*60
COOKIE_NAME = 'visitors_v1'


def require_post_and_authorization(view):
  def wrapper(request):
    if request.method != 'POST':
      log.warning('Wrong method.')
      return HttpResponseRedirect(reverse('worktime_main'))
    if not is_authorized(request):
      return HttpResponseRedirect(reverse('worktime_main'))
    return view(request)
  return wrapper


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
  for era in Era.objects.filter(current=False):
    era_dict = {'id':era.id}
    if era.description:
      era_dict['name'] = era.description[:22]
    else:
      era_dict['name'] = str(era.id)
    summary['eras'].append(era_dict)
  if params['format'] == 'html':
    summary['authorized'] = is_authorized(request)
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
@require_post_and_authorization
def switch(request):
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
@require_post_and_authorization
def adjust(request):
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

@require_post_and_authorization
def switchera(request):
  params = QueryParams()
  params.add('era', type=int)
  params.add('new-era')
  params.parse(request.POST)
  work_times = WorkTimesDatabase()
  if params['new-era']:
    work_times.clear(params['new-era'])
  elif params['era'] is not None:
    work_times.switch_era(params['era'])
  return HttpResponseRedirect(reverse('worktime_main'))

@csrf_exempt
@require_post_and_authorization
def clear(request):
  work_times = WorkTimesDatabase()
  work_times.clear()
  return HttpResponseRedirect(reverse('worktime_main'))


##### Helper functions #####

def is_authorized(request):
  cookie_value = request.COOKIES.get(COOKIE_NAME)
  try:
    authorized_cookie = AuthorizedCookie.objects.get(name=COOKIE_NAME, value=cookie_value)
  except AuthorizedCookie.DoesNotExist:
    log.warning('Unauthorized visitor (cookie {}={}).'.format(COOKIE_NAME, cookie_value))
    return False
  if authorized_cookie:
    return True
