import logging
from django.shortcuts import render, reverse
from django.http import HttpResponseRedirect
from .worktime import WorkTimes, timestring
log = logging.getLogger(__name__)


##### Views #####

def main(request):
  work_times = WorkTimes(data_store='database')
  summary = work_times.get_summary()
  summary['modes'] = work_times.modes
  return render(request, 'worktime/main.tmpl', summary)

def switch(request):
  mode = request.POST.get('mode')
  work_times = WorkTimes(data_store='database')
  if mode is None or mode not in work_times.modes:
    log.warning('Invalid or missing mode {!r}.'.format(mode))
    return HttpResponseRedirect(reverse('worktime:main'))
  old_mode, old_elapsed = work_times.switch_mode(mode)
  return HttpResponseRedirect(reverse('worktime:main'))

def adjust(request):
  mode = request.POST.get('mode')
  delta_str = request.POST.get('delta')
  if not (mode and delta_str):
    log.warning('Invalid mode ({!r}) and/or delta ({!r}).'.format(mode, delta_str))
    return HttpResponseRedirect(reverse('worktime:main'))
  try:
    delta = 60*int(delta_str)
  except ValueError:
    log.warning('Invalid delta {!r}.'.format(mode, delta_str))
    return HttpResponseRedirect(reverse('worktime:main'))
  work_times = WorkTimes(data_store='database')
  work_times.add_elapsed(mode, delta)
  return HttpResponseRedirect(reverse('worktime:main'))

def clear(request):
  if not getattr(request, 'POST', None):
    log.warning('Wrong method.')
    return HttpResponseRedirect(reverse('worktime:main'))
  work_times = WorkTimes(data_store='database')
  work_times.clear()
  return HttpResponseRedirect(reverse('worktime:main'))
