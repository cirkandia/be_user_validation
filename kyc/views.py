import json
import hmac
import hashlib
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view

from .models import KYCRequest
from .utils.didit_client import create_session, retrieve_session, update_session_status

def kyc_test(request):
    return render(request, "kyc/test.html")

class DiditKYCAPIView(APIView):
    """
    POST /kyc/api/kyc/
    Crea una nueva sesión KYC en Didit y la almacena localmente.
    """
    def post(self, request):
        data = request.data
        print("🔹 Datos recibidos:", data)
        
        if not data.get("full_name") or not data.get("document_id"):
            return Response({"error": "Faltan campos 'full_name' y 'document_id'."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Registrar localmente en la base de datos
        kyc_request = KYCRequest.objects.create(
            full_name=data["full_name"],
            document_id=data["document_id"],
            status="pending"
        )

        # Parámetros para Didit
        features = data.get("features", "OCR")
        tunnel_url = getattr(settings, "TUNNEL_URL", None)
        callback_url = f"{tunnel_url}/kyc/api/webhook/" if tunnel_url else "https://tuservidor.com/kyc/api/webhook/"
        vendor_data = data.get("vendor_data", data["document_id"])

        print("🔹 Callback URL:", callback_url)

        try:
            session_data = create_session(features, callback_url, vendor_data)
            print("🔹 Respuesta create_session:", session_data)
            
            # Actualizar con el session_id de la respuesta
            # La API de Didit devuelve session_id, no id
            kyc_request.session_id = session_data["session_id"]
            kyc_request.save()

            # Crear respuesta basada en los campos realmente disponibles
            response_data = {
                "message": "Sesión KYC creada con éxito",
                "session_id": session_data["session_id"],
                "verification_url": session_data["url"]
            }
            
            # Añadir campos opcionales si están disponibles
            if "expires_at" in session_data:
                response_data["expires_at"] = session_data["expires_at"]
            else:
                # Usar un valor ficticio para expires_at si no está en la respuesta
                from datetime import datetime, timedelta
                response_data["expires_at"] = (datetime.now() + timedelta(days=7)).isoformat()
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            print("❌ Error en DiditKYCAPIView:", str(e))
            kyc_request.delete()
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
def didit_webhook(request):
    """
    POST /kyc/api/webhook/
    Endpoint para recibir actualizaciones de estado de Didit.
    """
    print("✅ Webhook recibido!")
    print(f"Datos recibidos: {request.body.decode('utf-8')}")
    
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    # Verificar la firma si está configurado el secreto del webhook
    if hasattr(settings, 'DIDIT_WEBHOOK_SECRET') and settings.DIDIT_WEBHOOK_SECRET:
        signature = request.headers.get("X-Signature")
        if not signature:
            return JsonResponse({"error": "Falta la firma en X-Signature"}, status=400)

        expected_signature = hmac.new(
            settings.DIDIT_WEBHOOK_SECRET.encode(),
            request.body,
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_signature):
            return JsonResponse({"error": "Firma inválida"}, status=401)

    try:
        data = json.loads(request.body)
        
        # La API puede devolver id o session_id
        session_id = data.get("session_id") or data.get("id")
        didit_status = data.get("status")

        if not session_id or not didit_status:
            return JsonResponse({"error": "Datos incompletos (session_id/id, status)"}, status=400)

        try:
            kyc_request = KYCRequest.objects.get(session_id=session_id)
            kyc_request.status = didit_status.lower()
            kyc_request.save()
            
            print(f"✅ Webhook procesado: Sesión {session_id}, Estado: {didit_status}")
            
        except KYCRequest.DoesNotExist:
            return JsonResponse({"error": "Sesión no encontrada"}, status=404)

        return JsonResponse({"message": "Webhook procesado", "status": didit_status})
    except Exception as e:
        print(f"❌ Error al procesar webhook: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)

class RetrieveSessionAPIView(APIView):
    """
    GET /kyc/api/retrieve/<session_id>/
    Recupera la información actual de una sesión en Didit.
    """
    def get(self, request, session_id):
        try:
            data = retrieve_session(session_id)
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UpdateStatusAPIView(APIView):
    """
    PATCH /kyc/api/update-status/<session_id>/
    Permite actualizar manualmente el estado en Didit.
    """
    def patch(self, request, session_id):
        new_status = request.data.get("status")
        if not new_status:
            return Response({"error": "Falta 'status' en la solicitud"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            updated_data = update_session_status(session_id, new_status)
            return Response(updated_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["GET"])
def kyc_status(request, session_id=None, document_id=None):
    """
    GET /kyc/api/status/?session_id=xxx
    GET /kyc/api/status/?document_id=xxx
    Retorna el estado de la solicitud KYC almacenado localmente.
    """
    if session_id:
        kyc_request = KYCRequest.objects.filter(session_id=session_id).first()
    elif document_id:
        kyc_request = KYCRequest.objects.filter(document_id=document_id).order_by("-created_at").first()
    else:
        return Response({"error": "Proporciona 'session_id' o 'document_id' en la querystring"},
                        status=status.HTTP_400_BAD_REQUEST)

    if not kyc_request:
        return Response({"error": "No se encontró la solicitud"}, status=status.HTTP_404_NOT_FOUND)

    return Response({
        "full_name": kyc_request.full_name,
        "document_id": kyc_request.document_id,
        "session_id": kyc_request.session_id,
        "status": kyc_request.status,
        "created_at": kyc_request.created_at.isoformat(),
        "updated_at": kyc_request.updated_at.isoformat()
    }, status=status.HTTP_200_OK)
