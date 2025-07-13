from django.urls import path
from .views import IndexAPIView

app_name = 'run'
urlpatterns = [
    path('', IndexAPIView.as_view(), name='index')
]