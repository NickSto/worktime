from django.conf.urls import url

from . import views

app_name = 'worktime'

urlpatterns = [
  url(r'^$', views.main, name='main'),
  url(r'switch$', views.switch, name='switch'),
  url(r'adjust$', views.adjust, name='adjust'),
  url(r'switchera$', views.switchera, name='switchera'),
  url(r'renamera$', views.renamera, name='renamera'),
  url(r'clear$', views.clear, name='clear'),
  url(r'settings$', views.settings, name='settings'),
]
