import requests
import hmac
import hashlib
import json
import os
import base64
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import KYCRequest
from rest_framework.decorators import api_view

# URLs base de Didit
BASE_URL = "https://api.didit.me"
AUTH_URL = "https://apx.didit.me/auth/v2/token/"

def get_client_token():
    """
    Obtiene el token de acceso de Didit usando autenticación Basic.
    """
    try:
        credentials = f"{settings.DIDIT_CLIENT_ID}:{settings.DIDIT_CLIENT_SECRET}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        data = {"grant_type": "client_credentials"}

        response = requests.post(AUTH_URL, headers=headers, data=data)

        print(f"🔹 Token Request Status: {response.status_code}")
        print(f"🔹 Token Response: {response.text[:500]}")  # Muestra parte de la respuesta

        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as error:
        print(f"❌ Error obteniendo token de Didit: {error}")
        return None

def create_session(features: str, callback: str, vendor_data: dict = None):
    """
    Crea una sesión de verificación KYC en Didit.
    """
    url = f"{BASE_URL}/v1/session/"
    token_data = get_client_token()

    if not token_data:
        raise Exception("No se pudo obtener el token de acceso")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token_data.get('access_token')}"
    }

    body = {
        "features": features,
        "callback": callback,
        "vendor_data": vendor_data or {}
    }

    response = requests.post(url, headers=headers, json=body)
    
    print(f"🔹 Creando sesión KYC en {url}")
    print(f"🔹 Datos enviados: {json.dumps(body, indent=2)}")
    print(f"🔹 Respuesta Status: {response.status_code}")
    print(f"🔹 Respuesta: {response.text[:500]}")

    response.raise_for_status()
    return response.json()

class DiditKYCAPIView(APIView):
    def post(self, request):
        """
        Endpoint para crear una nueva sesión de verificación KYC en Didit.
        """
        data = request.data

        if not data.get("full_name") or not data.get("document_id"):
            return Response({"error": "Se requieren 'full_name' y 'document_id'"},
                            status=status.HTTP_400_BAD_REQUEST)

        callback_url = f"{os.getenv('TUNNEL_URL')}/kyc/api/webhook/"

        vendor_data = {
            "reference_id": data.get("document_id"),
            "customer_name": data.get("full_name")
        }

        kyc_request = KYCRequest.objects.create(
            full_name=data["full_name"],
            document_id=data["document_id"],
            status="pending"
        )

        try:
            session_result = create_session(
                features=data.get("features", "FACE,OCR"),
                callback=callback_url,
                vendor_data=vendor_data
            )

            kyc_request.session_id = session_result.get("id")
            kyc_request.save()

            return Response({
                "message": "Sesión KYC creada con éxito",
                "session_id": session_result.get("id"),
                "verification_url": session_result.get("url"),
                "expires_at": session_result.get("expires_at")
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            kyc_request.delete()
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
def didit_webhook(request):
    """
    Webhook de Didit para actualizar el estado de verificación KYC.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    payload = request.body
    signature = request.headers.get("X-Signature")

    if not signature:
        return JsonResponse({"error": "Falta la firma"}, status=400)

    expected_signature = hmac.new(
        settings.DIDIT_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_signature):
        return JsonResponse({"error": "Firma inválida"}, status=401)

    try:
        data = json.loads(payload)
        session_id = data.get("id")
        status_didit = data.get("status")

        if not session_id or not status_didit:
            return JsonResponse({"error": "Datos incompletos"}, status=400)

        estados_mapeados = {
            "PENDING": "pending",
            "COMPLETED": "approved",
            "REJECTED": "rejected",
            "FAILED": "failed",
            "EXPIRED": "expired"
        }
        estado_mapeado = estados_mapeados.get(status_didit, "pending")

        kyc_request = KYCRequest.objects.filter(session_id=session_id).first()
        if not kyc_request:
            return JsonResponse({"error": "Sesión no encontrada"}, status=404)

        kyc_request.status = estado_mapeado
        kyc_request.save()

        return JsonResponse({"message": "Webhook procesado", "status": estado_mapeado})

    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@api_view(['GET'])
def kyc_status(request, session_id=None, document_id=None):
    """
    Obtiene el estado de una verificación KYC usando session_id o document_id.
    """
    kyc = None
    if session_id:
        kyc = KYCRequest.objects.filter(session_id=session_id).first()
    elif document_id:
        kyc = KYCRequest.objects.filter(document_id=document_id).order_by('-created_at').first()

    if not kyc:
        return Response({"error": "No se encontró la solicitud"}, status=status.HTTP_404_NOT_FOUND)

    return Response({
        "full_name": kyc.full_name,
        "document_id": kyc.document_id,
        "session_id": kyc.session_id,
        "status": kyc.status,
        "created_at": kyc.created_at.isoformat(),
        "updated_at": kyc.updated_at.isoformat()
    })
