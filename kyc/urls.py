from django.urls import path
from .views import DiditKYCAPIView, didit_webhook, kyc_status
from django.views.generic import TemplateView

app_name = 'kyc'  # Añadir esto para usar el namespace

urlpatterns = [
    path('api/kyc/', DiditKYCAPIView.as_view(), name='didit_kyc'),
    path('api/webhook/', didit_webhook, name='didit_webhook'),
    path('api/status/session/<str:session_id>/', kyc_status, name='kyc_status_session'),
    path('api/status/document/<str:document_id>/', kyc_status, name='kyc_status_document'),
    path('test/', TemplateView.as_view(template_name='kyc/test.html'), name='kyc_test'),
]