from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.shortcuts import redirect

# Función simple para redirigir a la página de prueba de KYC
def home_view(request):
    return redirect('kyc:kyc_test')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('kyc/', include('kyc.urls', namespace='kyc')),
    path('', home_view, name='home'),  # Redirige a la página de prueba KYC
]