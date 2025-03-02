import requests
import hmac
import hashlib
import json
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import KYCRequest

DIDIT_BASE_URL = "https://api.didit.me"

# Función para obtener el token de Didit
def get_didit_token():
    url = f"{DIDIT_BASE_URL}/oauth/token"
    data = {
        "client_id": settings.DIDIT_CLIENT_ID,
        "client_secret": settings.DIDIT_CLIENT_SECRET,
        "grant_type": "client_credentials"
    }
    response = requests.post(url, json=data)
    if response.status_code == 200:
        return response.json().get("access_token")
    return None

# API para crear una sesión de verificación KYC en Didit
class DiditKYCAPIView(APIView):
    def post(self, request):
        token = get_didit_token()
        if not token:
            return Response({"error": "Failed to get access token"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        data = request.data
        kyc_request = KYCRequest.objects.create(
            full_name=data.get("full_name"),
            document_id=data.get("document_id"),
            status="pending"
        )

        # Crear la sesión en Didit
        headers = {"Authorization": f"Bearer {token}"}
        didit_data = {
            "full_name": data.get("full_name"),
            "document_id": data.get("document_id")
        }
        response = requests.post(f"{DIDIT_BASE_URL}/identity-verification/sessions", json=didit_data, headers=headers)

        if response.status_code == 201:
            session_id = response.json().get("session_id")
            kyc_request.session_id = session_id
            kyc_request.save()
            return Response({"message": "KYC session created", "session_id": session_id}, status=status.HTTP_201_CREATED)
        else:
            return Response({"error": "Failed to create session"}, status=response.status_code)

# API para recibir Webhooks de Didit
@csrf_exempt
def didit_webhook(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    # Validar la firma del webhook
    received_signature = request.headers.get("X-Signature")
    if not received_signature:
        return JsonResponse({"error": "Missing signature"}, status=403)

    secret_key = settings.DIDIT_WEBHOOK_SECRET.encode()
    payload = request.body

    expected_signature = hmac.new(secret_key, payload, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(received_signature, expected_signature):
        return JsonResponse({"error": "Invalid signature"}, status=403)

    data = json.loads(payload)
    session_id = data.get("session_id")
    status_update = data.get("status")

    # Actualizar estado en la base de datos
    try:
        kyc_request = KYCRequest.objects.get(session_id=session_id)
        kyc_request.status = status_update
        kyc_request.save()
    except KYCRequest.DoesNotExist:
        return JsonResponse({"error": "Session ID not found"}, status=404)

    return JsonResponse({"message": "Webhook received successfully"}, status=200)
