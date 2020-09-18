from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='Open Layer'),
	path('callback', views.callback, name='Open Layer Response'),
]
