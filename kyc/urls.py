from django.urls import path, include
from .views import (
    DiditKYCAPIView,
    didit_webhook,
    RetrieveSessionAPIView,
    UpdateStatusAPIView,
    kyc_status,
    kyc_test
)

app_name = "kyc"

urlpatterns = [
    path("api/kyc/", DiditKYCAPIView.as_view(), name="didit_create_session"),
    path("api/webhook/", didit_webhook, name="didit_webhook"),
    path("api/retrieve/<str:session_id>/", RetrieveSessionAPIView.as_view(), name="didit_retrieve_session"),
    path("api/update-status/<str:session_id>/", UpdateStatusAPIView.as_view(), name="didit_update_status"),
    path("api/status/", kyc_status, name="didit_local_status"),
    path("test/", kyc_test, name="kyc_test"),
]
