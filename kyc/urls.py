from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    DiditKYCAPIView,
    didit_webhook,
    RetrieveSessionAPIView,
    UpdateStatusAPIView,
    kyc_test,
)

app_name = "kyc"

urlpatterns = [
    # Rutas JWT
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    
    
    path("api/kyc/", DiditKYCAPIView.as_view(), name="didit_create_session"),
    path("api/webhook/", didit_webhook, name="didit_webhook"),
    path("api/retrieve/<str:session_id>/", RetrieveSessionAPIView.as_view(), name="didit_retrieve_session"),
    path("api/update-status/<str:session_id>/", UpdateStatusAPIView.as_view(), name="didit_update_status"),
    path("test/", kyc_test, name="kyc_test"),
]
