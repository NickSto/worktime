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
  params.add('format', choices=('html', 'plain'), default='html')
  params.parse(request.GET)
  work_times = WorkTimes(data_store='database')
  summary = work_times.get_summary()
  summary['modes'] = work_times.modes
  if params['format'] == 'html':
    return render(request, 'worktime/main.tmpl', summary)
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
  work_times = WorkTimes(data_store='database')
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
  work_times = WorkTimes(data_store='database')
  params = QueryParams()
  params.add('mode', choices=work_times.modes)
  params.add('delta', type=int)
  params.parse(request.POST)
  if not (params['mode'] and params['delta']) or params.invalid_value:
    log.warning('Invalid mode ({!r}) and/or delta ({!r}).'.format(mode, delta_str))
    return HttpResponseRedirect(reverse('worktime_main'))
  work_times.add_elapsed(params['mode'], params['delta']*60)
  return HttpResponseRedirect(reverse('worktime_main'))

@csrf_exempt
def clear(request):
  if request.method != 'POST':
    log.warning('Wrong method.')
    return HttpResponseRedirect(reverse('worktime_main'))
  work_times = WorkTimes(data_store='database')
  work_times.clear()
  return HttpResponseRedirect(reverse('worktime_main'))
