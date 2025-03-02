from django.urls import path
from .views import DiditAPIView

urlpatterns = [
    path('api/didit/', DiditAPIView.as_view(), name='didit_api'),
]