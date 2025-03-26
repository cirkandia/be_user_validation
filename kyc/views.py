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
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view

from .models import UserDetails, SessionDetails
from .utils.didit_client import create_session, retrieve_session, update_session_status

def kyc_test(request):
    return render(request, "kyc/test.html")

class DiditKYCAPIView(APIView):
    """
    POST /kyc/api/kyc/
    Crea una nueva sesión KYC en Didit y la almacena localmente.
    """
    permission_classes = [IsAuthenticated]
    def post(self, request):
        data = request.data
        print("🔹 Datos recibidos:", data)
        
        if not data.get("first_name") or not data.get("last_name") or not data.get("document_id"):
            return Response({"error": "Faltan campos 'first_name', 'last_name' o 'document_id'."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Registrar datos personales localmente en la base de datos
        personal_data = UserDetails.objects.create(
            first_name=data["first_name"],
            last_name=data["last_name"],
            document_id=data["document_id"]
        )

        # Registrar detalles de la sesión localmente en la base de datos
        session_details = SessionDetails.objects.create(
            personal_data=personal_data,
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
            
            # Actualizar el registro con todos los datos de la sesión
            session_details.session_id = session_data["session_id"]
            session_details.save()

            # Crear respuesta
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
            personal_data.delete()
            session_details.delete()
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

    try:
        data = json.loads(request.body)
        
        # Extraer datos principales
        session_id = data.get("session_id") or data.get("id")
        didit_status = data.get("status")

        if not session_id or not didit_status:
            return JsonResponse({"error": "Datos incompletos (session_id/id, status)"}, status=400)

        try:
            session_details = SessionDetails.objects.get(session_id=session_id)
            
            # Actualizar el estado
            session_details.status = didit_status.lower()
            
            # Guardar la nacionalidad, fecha de nacimiento y tipo de documento si están disponibles
            kyc_data = data.get("decision", {}).get("kyc", {})
            personal_data = session_details.personal_data
            personal_data.nationality = kyc_data.get("issuing_state_name")
            date_of_birth = kyc_data.get("date_of_birth")
            document_type = kyc_data.get("document_type")
            document_id = kyc_data.get("document_number")
            last_name = kyc_data.get("last_name")
            if document_id:
                personal_data.document_id = document_id
            if date_of_birth:
                personal_data.date_of_birth = date_of_birth
            if document_type:
                personal_data.document_type = document_type
            if last_name:
                personal_data.last_name = last_name
            personal_data.save()
            
            # Si el estado es "completed", obtener la decisión completa
            if didit_status.upper() == "COMPLETED":
                try:
                    decision_data = retrieve_session(session_id)
                    print(f"✅ Datos de decisión recuperados para sesión {session_id}")
                except Exception as e:
                    print(f"⚠️ Error al recuperar decisión completa: {str(e)}")
                    # No fallar el webhook si esto falla
            
            session_details.save()
            print(f"✅ Webhook procesado: Sesión {session_id}, Estado: {didit_status}")
            
        except SessionDetails.DoesNotExist:
            return JsonResponse({"error": "Sesión no encontrada"}, status=404)

        return JsonResponse({
            "message": "Webhook procesado", 
            "status": didit_status,
            "session_id": session_id
        })
    except Exception as e:
        print(f"❌ Error al procesar webhook: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)

class RetrieveSessionAPIView(APIView):
    """
    GET /kyc/api/retrieve/<session_id>/
    Recupera la información actual de una sesión en Didit.
    """
    permission_classes = [IsAuthenticated]
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
    permission_classes = [IsAuthenticated]
    def patch(self, request, session_id):
        new_status = request.data.get("status")
        if not new_status:
            return Response({"error": "Falta 'status' en la solicitud"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            updated_data = update_session_status(session_id, new_status)
            return Response(updated_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


