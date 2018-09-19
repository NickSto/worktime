import json
import logging
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, reverse
from django.views.decorators.csrf import csrf_exempt
from .worktime import WorkTimes, timestring
from utils import QueryParams, boolish
log = logging.getLogger(__name__)


##### Views #####

def main(request):
  params = QueryParams()
  params.add('format', choices=('html', 'plain', 'json'), default='html')
  params.parse(request.GET)
  work_times = WorkTimes(backend='database')
  summary = work_times.get_summary()
  summary['modes'] = work_times.modes
  if params['format'] == 'html':
    return render(request, 'worktime/main.tmpl', summary)
  elif params['format'] == 'json':
    return HttpResponse(json.dumps(summary), content_type=settings.PLAINTEXT)
  elif params['format'] == 'plain':
    lines = []
    lines.append('status\t{current_mode}\t{current_elapsed}'.format(**summary))
    for elapsed in summary['elapsed']:
      lines.append('total\t{mode}\t{time}'.format(**elapsed))
    if summary['ratio'] is not None:
      lines.append('ratio\t{ratio_str}\t{ratio}'.format(**summary))
    return HttpResponse('\n'.join(lines), content_type=settings.PLAINTEXT)

@csrf_exempt
def switch(request):
  if request.method != 'POST':
    log.warning('Wrong method.')
    return HttpResponseRedirect(reverse('worktime_main'))
  work_times = WorkTimes(backend='database')
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
  work_times = WorkTimes(backend='database')
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

@csrf_exempt
def clear(request):
  if request.method != 'POST':
    log.warning('Wrong method.')
    return HttpResponseRedirect(reverse('worktime_main'))
  work_times = WorkTimes(backend='database')
  work_times.clear()
  return HttpResponseRedirect(reverse('worktime_main'))
