import json
import logging
import time
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, reverse
from django.views.decorators.csrf import csrf_exempt
from .models import Era, Period, User, Cookie
from .worktime import MODES, WorkTimesDatabase, timestring
from utils.queryparams import QueryParams, boolish
log = logging.getLogger(__name__)

HISTORY_BAR_TIMESPAN = 2*60*60
COOKIE_NAME = 'visitors_v1'
DEFAULT_ERA_NAME = 'Project 1'
COLORS = {'p':'red', 'w':'green', 'n':'bluegray'}
OPPOSITES = {'p':'w', 'w':'p'}

#TODO: Improve experience for first-time visitors:
#      1. Write some introduction at the top.
#      2. Let's have a button or something to create a demo `Era` (name it "Big Project" or
#         something) that shows off all the features.

#TODO: A way for users to link their devices.
#      I'd hate to institute a username/password system, so how about alternatives?
#      One idea is to generate a one-use code that they enter on a device.
#      I could have a button that the user clicks to generate a code, and then they enter it on
#      the other device. The `User` of the device that generated the code is now associated with
#      both `Cookie`s. Once they enter it on the other device (or after a limited time, like 10 min)
#      the code is deactivated.
#      The codes could be a series of words randomly chosen from the EFF diceware dictionary.
#      I could store it as a field on the `User` model, along with a timestamp field so I know when
#      to expire it.


def require_post_and_cookie(view):
  def wrapper(request):
    if request.method != 'POST':
      log.warning('Wrong method.')
      return HttpResponseRedirect(reverse('worktime_main'))
    if not request.COOKIES.get(COOKIE_NAME):
      log.warning('User sent no {!r} cookie.'.format(COOKIE_NAME))
      return HttpResponseRedirect(reverse('worktime_main'))
    return view(request)
  return wrapper


##### Views #####

def main(request):
  params = QueryParams()
  params.add('format', choices=('html', 'plain', 'json'), default='html')
  params.add('numbers', choices=('values', 'text'), default='text')
  params.add('debug', type=boolish)
  params.parse(request.GET)
  user = get_user(request)
  work_times = WorkTimesDatabase(user)
  summary = work_times.get_summary(numbers=params['numbers'], timespans=(12*60*60, 2*60*60))
  summary['debug'] = params['debug']
  summary['meta'] = {'colors':COLORS, 'opposites':OPPOSITES}
  if params['format'] == 'html':
    apply_colors(summary, COLORS)
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
@require_post_and_cookie
def switch(request):
  params = QueryParams()
  params.add('mode', choices=MODES)
  params.add('debug', type=boolish)
  params.add('site')
  params.parse(request.POST)
  if params['site']:
    return warn_and_redirect_spambot('switch', params['site'], reverse('worktime_main'))
  if params.invalid_value:
    log.warning('Invalid parameter.')
    return HttpResponseRedirect(reverse('worktime_main'))
  user = get_or_create_user(request)
  assert user is not None
  work_times = WorkTimesDatabase(user)
  era = get_or_create_era(user, DEFAULT_ERA_NAME)
  old_mode, old_elapsed = work_times.switch_mode(params['mode'], era=era)
  if params['debug']:
    query_str = '?debug=true'
  else:
    query_str = ''
  return HttpResponseRedirect(reverse('worktime_main')+query_str)

@csrf_exempt
@require_post_and_cookie
def adjust(request):
  params = QueryParams()
  params.add('mode', choices=MODES)
  params.add('add', type=int)
  params.add('subtract', type=int)
  params.add('debug', type=boolish)
  params.add('site')
  params.parse(request.POST)
  if params['site']:
    return warn_and_redirect_spambot('adjust', params['site'], reverse('worktime_main'))
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
  user = get_or_create_user(request)
  assert user is not None
  work_times = WorkTimesDatabase(user)
  era = get_or_create_era(user, DEFAULT_ERA_NAME)
  work_times.add_elapsed(params['mode'], delta*60, era=era)
  if params['debug']:
    query_str = '?debug=true'
  else:
    query_str = ''
  return HttpResponseRedirect(reverse('worktime_main')+query_str)

@require_post_and_cookie
def switchera(request):
  params = QueryParams()
  params.add('era', type=int)  # This is the Era.id (primary key).
  params.add('new-era')        # This is a name for the new Era.
  params.add('debug', type=boolish)
  params.add('site')
  params.parse(request.POST)
  if params['site']:
    return warn_and_redirect_spambot('switchera', params['site'], reverse('worktime_main'))
  user = get_or_create_user(request)
  assert user is not None
  work_times = WorkTimesDatabase(user)
  if params['new-era']:
    existing_eras = Era.objects.filter(user=user, description=params['new-era'])
    if existing_eras.count() > 0:
      log.warning('User tried to create a new Era with the same name as an existing one ({!r})'
                  .format(params['new-era']))
      dest_era_id = existing_eras[0].id
    else:
      dest_era = Era(user=user, current=False, description=params['new-era'])
      dest_era.save()
      dest_era_id = dest_era.id
  else:
    dest_era_id = params['era']
  if dest_era_id is not None:
    work_times.switch_era(id=dest_era_id)
  if params['debug']:
    query_str = '?debug=true'
  else:
    query_str = ''
  return HttpResponseRedirect(reverse('worktime_main')+query_str)

@csrf_exempt
@require_post_and_cookie
def clear(request):
  user = get_or_create_user(request)
  assert user is not None
  work_times = WorkTimesDatabase(user)
  work_times.clear()
  return HttpResponseRedirect(reverse('worktime_main'))

@require_post_and_cookie
def settings(request):
  params = QueryParams()
  for setting in User.SETTINGS:
    params.add(setting, choices=('on', 'off'))
  params.add('site')
  params.parse(request.POST)
  if params['site']:
    return warn_and_redirect_spambot('switchera', params['site'], reverse('worktime_main'))
  if params.invalid_value:
    log.warning('Invalid parameter.')
    return HttpResponseRedirect(reverse('worktime_main'))
  user = get_or_create_user(request)
  assert user is not None
  changed = False
  for setting in User.SETTINGS:
    if params[setting] is None:
      continue
    new_value = params[setting] == 'on'
    current_value = getattr(user, setting, None)
    if new_value != current_value:
      log.info('Changing setting {!r} for user {} to {!r}'.format(setting, user, new_value))
      setattr(user, setting, new_value)
      changed = True
  if changed:
    user.save()
  return HttpResponseRedirect(reverse('worktime_main'))


##### Helper functions #####

def apply_colors(summary, colors):
  summary['current_color'] = colors.get(summary['current_mode'])
  for period in summary['history']['periods']:
    period['color'] = colors.get(period['mode'])
  for adjustment in summary['history']['adjustments']:
    if adjustment['sign'] == '-' and adjustment['mode'] in OPPOSITES:
      adjustment['color'] = colors.get(OPPOSITES[adjustment['mode']])
    else:
      adjustment['color'] = colors.get(adjustment['mode'])

def get_user(request):
  cookie_value = request.COOKIES.get(COOKIE_NAME)
  try:
    cookie = Cookie.objects.get(name=COOKIE_NAME, value=cookie_value)
  except Cookie.DoesNotExist:
    return None
  return cookie.user

def get_or_create_user(request):
  user = get_user(request)
  if user:
    return user
  cookie_value = request.COOKIES.get(COOKIE_NAME)
  if not cookie_value:
    return None
  user = User()
  user.save()
  cookie = Cookie(user=user, name=COOKIE_NAME, value=cookie_value)
  cookie.save()
  return user

def get_or_create_era(user, default_name):
  era, created = Era.objects.get_or_create(user=user, current=True)
  if created:
    era.description = default_name
    era.save()
  return era

def warn_and_redirect_spambot(action, site, view_url=None):
  site_trunc = truncate(site)
  log.warning('Spambot blocked from worktime action {!r}. It entered "site" form value {!r}.'
              .format(action, site_trunc))
  if view_url is not None:
    return HttpResponseRedirect(view_url)

def truncate(s, max_len=100):
  if s is not None and len(s) > max_len:
    return s[:max_len]+'...'
  else:
    return s
