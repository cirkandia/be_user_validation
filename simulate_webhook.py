import requests
import hmac
import hashlib
import json
import os
import sys
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración
webhook_secret = os.getenv('DIDIT_WEBHOOK_SECRET')
if not webhook_secret:
    print("Error: DIDIT_WEBHOOK_SECRET no está definido en el archivo .env")
    sys.exit(1)

# Solicitar información
print("=== SIMULADOR DE WEBHOOK DIDIT ===\n")
tunnel_url = input("URL del túnel (ej: https://tu-subdominio.trycloudflare.com): ")
if not tunnel_url:
    print("Error: Debes proporcionar una URL de túnel")
    sys.exit(1)

# Eliminar la barra final si existe
tunnel_url = tunnel_url.rstrip('/')

# Construir la URL del webhook
webhook_url = f"{tunnel_url}/kyc/api/webhook/"

# Solicitar el session_id
session_id = input("ID de sesión (obligatorio): ")
if not session_id:
    print("Error: El ID de sesión es obligatorio")
    sys.exit(1)

# Seleccionar estado
print("\nEstados disponibles:")
print("1. COMPLETED (verificación exitosa)")
print("2. REJECTED (verificación rechazada)")
print("3. FAILED (verificación fallida)")
print("4. EXPIRED (verificación expirada)")
print("5. PENDING (en proceso)")

option = input("\nSelecciona una opción (1-5) [1]: ") or "1"
statuses = {
    "1": "COMPLETED", 
    "2": "REJECTED", 
    "3": "FAILED", 
    "4": "EXPIRED",
    "5": "PENDING"
}
status = statuses.get(option, "COMPLETED")

# Construir el payload
payload = {
    "id": session_id,
    "status": status,
    "timestamp": "2025-03-03T16:30:00Z"
}

# Añadir datos adicionales para pruebas
if status == "COMPLETED":
    payload["vendor_data"] = {
        "verification_result": "success",
        "customer_id": input("ID de cliente (opcional): ") or "test123"
    }
elif status in ["REJECTED", "FAILED"]:
    payload["vendor_data"] = {
        "verification_result": "failure",
        "reason": input("Razón del rechazo (opcional): ") or "Documento no válido"
    }

# Serializar a JSON
payload_json = json.dumps(payload).encode()

# Calcular firma HMAC
signature = hmac.new(
    webhook_secret.encode(),
    payload_json,
    hashlib.sha256
).hexdigest()

# Cabeceras
headers = {
    "Content-Type": "application/json",
    "X-Signature": signature
}

print("\nEnviando webhook...")
print(f"URL: {webhook_url}")
print(f"Payload: {json.dumps(payload, indent=2)}")
print(f"Firma: {signature}")

try:
    # Enviar la solicitud
    response = requests.post(webhook_url, data=payload_json, headers=headers)
    
    # Mostrar resultados
    print(f"\nCódigo de respuesta: {response.status_code}")
    print(f"Respuesta: {response.text}")
    
    if response.status_code == 200:
        print("\n✅ ¡Webhook procesado correctamente!")
    else:
        print("\n❌ Error al procesar el webhook")
except Exception as e:
    print(f"\n❌ Error al enviar el webhook: {str(e)}")