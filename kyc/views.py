import requests
import hmac
import hashlib
import json
import uuid
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import KYCRequest
import os
from rest_framework.decorators import api_view

# URLs de Didit
DIDIT_AUTH_URL = "https://auth.didit.me/oauth/token"
DIDIT_SESSION_URL = "https://verification.didit.me/v1/session"  # Sin barra final

# Obtener el token de acceso de Didit
def obtener_token_acceso():
    datos = {
        "client_id": settings.DIDIT_CLIENT_ID,
        "client_secret": settings.DIDIT_CLIENT_SECRET,
        "grant_type": "client_credentials"
    }
    try:
        respuesta = requests.post(DIDIT_AUTH_URL, json=datos)
        respuesta.raise_for_status()
        return respuesta.json().get("access_token")
    except requests.exceptions.RequestException as error:
        print(f"Error al obtener el token de cliente: {error}")
        return None

# Crear una sesión de verificación en Didit
class DiditKYCAPIView(APIView):
    def post(self, request):
        token = obtener_token_acceso()
        if not token:
            return Response({"error": "No se pudo obtener el token de acceso"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        data = request.data
        
        # Validar campos requeridos para nuestro sistema
        if not data.get("full_name") or not data.get("document_id"):
            return Response(
                {"error": "Se requieren los campos 'full_name' y 'document_id'"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Configurar URL de callback real
        base_url = request.build_absolute_uri('/').rstrip('/')
        callback_url = f"{base_url}/kyc/api/webhook/"
        
        # Construir vendor_data como objeto JSON según la documentación
        vendor_data = {
            "customer_id": data.get("document_id"),
            "full_name": data.get("full_name"),
            "reference_id": str(uuid.uuid4())  # ID de referencia único
        }
        
        # Parámetros adicionales según documentación
        redirect_url = data.get("redirect_url")
        locale = data.get("locale", "es")  # Según docs es 'locale', no 'language'
        
        # Guardar en la base de datos la solicitud
        kyc_request = KYCRequest.objects.create(
            full_name=data.get("full_name"),
            document_id=data.get("document_id"),
            status="pending"
        )

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Construir payload según documentación exacta
        # https://docs.didit.me/identity-verification/api-reference/create-session
        didit_data = {
            "callback": callback_url,
            "vendor_data": vendor_data,  # La API acepta un objeto JSON directo
            "locale": locale
        }
        
        # Agregar campos opcionales solo si están presentes
        if redirect_url:
            didit_data["redirect"] = redirect_url
            
        # "features" es opcional según la documentación
        if "features" in data:
            # Valores permitidos: FACE, OCR, NFC, LIVENESS (o combinaciones)
            didit_data["features"] = data.get("features")

        try:
            # Realizar la solicitud POST a la URL correcta
            response = requests.post(DIDIT_SESSION_URL, json=didit_data, headers=headers)
            response.raise_for_status()
            session_data = response.json()
            
            # Actualizar registro con session_id
            kyc_request.session_id = session_data.get("id")  # Según docs es 'id', no 'session_id'
            kyc_request.save()
            
            # Devolver respuesta basada en la documentación
            return Response({
                "message": "Sesión KYC creada con éxito",
                "session_id": session_data.get("id"),
                "verification_url": session_data.get("url"),
                "expires_at": session_data.get("expires_at")  # Según docs es 'expires_at', no 'expiration'
            }, status=status.HTTP_201_CREATED)
        except requests.exceptions.RequestException as error:
            # Log error completo para diagnóstico
            print(f"Error completo al crear sesión Didit: {error}")
            
            # Si hay respuesta con mensaje de error, mostrarla
            error_detail = str(error)
            if hasattr(error, 'response') and error.response is not None:
                try:
                    error_detail = error.response.json()
                except:
                    error_detail = error.response.text
            
            # Actualizar a estado fallido en caso de error
            kyc_request.delete()  # Eliminar la solicitud fallida
            
            return Response({"error": f"Error al crear la sesión: {error_detail}"}, 
                           status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Webhook para recibir actualizaciones de Didit
@csrf_exempt
def didit_webhook(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    # Verificar firma según documentación
    firma_recibida = request.headers.get("X-Signature")
    if not firma_recibida:
        return JsonResponse({"error": "Firma no proporcionada"}, status=400)

    cuerpo = request.body
    firma_calculada = hmac.new(
        settings.DIDIT_WEBHOOK_SECRET.encode(),
        cuerpo,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(firma_recibida, firma_calculada):
        return JsonResponse({"error": "Firma inválida"}, status=403)

    try:
        datos = json.loads(cuerpo)
        session_id = datos.get("id")  # Según docs es 'id', no 'session_id'
        nuevo_estado = datos.get("status")
        
        if not session_id or not nuevo_estado:
            return JsonResponse({"error": "Datos incompletos en la solicitud"}, status=400)
        
        # Mapear los estados según la documentación:
        # https://docs.didit.me/identity-verification/api-reference/webhook
        estado_mapeado = "pending"
        if nuevo_estado == "COMPLETED":
            estado_mapeado = "approved"
        elif nuevo_estado in ["FAILED", "EXPIRED", "REJECTED"]:
            estado_mapeado = "rejected"
        
        try:
            kyc_request = KYCRequest.objects.get(session_id=session_id)
            kyc_request.status = estado_mapeado
            kyc_request.save()
            
            # Aquí podrías agregar lógica adicional según el estado
            
            return JsonResponse({
                "success": True,
                "message": "Webhook procesado correctamente",
                "status": estado_mapeado
            })
            
        except KYCRequest.DoesNotExist:
            return JsonResponse({"error": "Sesión no encontrada"}, status=404)
            
    except json.JSONDecodeError:
        return JsonResponse({"error": "Formato JSON inválido"}, status=400)

@api_view(['GET'])
def kyc_status(request, session_id=None, document_id=None):
    """
    Obtener el estado de una verificación KYC por session_id o document_id
    """
    if (session_id):
        try:
            kyc = KYCRequest.objects.get(session_id=session_id)
        except KYCRequest.DoesNotExist:
            return Response(
                {"error": "No se encontró ninguna solicitud con ese session_id"},
                status=status.HTTP_404_NOT_FOUND
            )
    elif (document_id):
        # Buscar la solicitud más reciente para este document_id
        try:
            kyc = KYCRequest.objects.filter(document_id=document_id).order_by('-created_at').first()
            if not kyc:
                return Response(
                    {"error": "No se encontró ninguna solicitud con ese document_id"},
                    status=status.HTTP_404_NOT_FOUND
                )
        except Exception as e:
            return Response(
                {"error": f"Error al buscar solicitud: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    else:
        return Response(
            {"error": "Debe proporcionar session_id o document_id"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    return Response({
        "full_name": kyc.full_name,
        "document_id": kyc.document_id,
        "session_id": kyc.session_id,
        "status": kyc.status,
        "created_at": kyc.created_at.isoformat(),
        "updated_at": kyc.updated_at.isoformat()
    })
