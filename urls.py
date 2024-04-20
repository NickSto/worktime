from django.urls import re_path

from . import views

app_name = 'worktime'

urlpatterns = [
  re_path(r'^$', views.main, name='main'),
  re_path(r'switch$', views.switch, name='switch'),
  re_path(r'adjust$', views.adjust, name='adjust'),
  re_path(r'switchera$', views.switchera, name='switchera'),
  re_path(r'renamera$', views.renamera, name='renamera'),
  re_path(r'clear$', views.clear, name='clear'),
  re_path(r'settings$', views.settings, name='settings'),
]
