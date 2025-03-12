import requests
import base64
from django.conf import settings

# Endpoint para obtener el token de acceso
AUTH_URL = "https://apx.didit.me/auth/v2/token/"

# Endpoint para crear la sesión de verificación
CREATE_SESSION_URL = "https://verification.didit.me/v1/session/"

# Endpoint para recuperar la decisión de la sesión (resultado de la verificación)
# Se debe formatear usando el session_id
RETRIEVE_DECISION_URL_TEMPLATE = "https://verification.didit.me/v1/session/{session_id}/decision/"

def get_client_token():
    try:
        # Combinar las credenciales
        credentials = f"{settings.DIDIT_CLIENT_ID}:{settings.DIDIT_CLIENT_SECRET}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {"grant_type": "client_credentials"}

        response = requests.post(AUTH_URL, headers=headers, data=data)
        print("🔹 Token Request Status:", response.status_code)
        print("🔹 Token Response:", response.text[:500])
        response.raise_for_status()
        token_data = response.json()
        return token_data.get("access_token")
    except requests.exceptions.RequestException as e:
        print(f"❌ Error al obtener token de Didit: {e}")
        if hasattr(e, "response") and e.response:
            print("Detalles:", e.response.text)
        return None

def create_session(features, callback_url, vendor_data):

    access_token = get_client_token()
    if not access_token:
        raise Exception("Error fetching client token")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    body = {
        "callback": callback_url,
        "features": features,
        "vendor_data": vendor_data
    }

    response = requests.post(CREATE_SESSION_URL, headers=headers, json=body)
    print("🔹 Creando sesión en Didit con datos:")
    print(body)
    print("🔹 Respuesta Status:", response.status_code)
    print("🔹 Respuesta:", response.text[:500])
    response.raise_for_status()
    return response.json()

def retrieve_session(session_id):
    access_token = get_client_token()
    if not access_token:
        raise Exception("Error fetching client token")

    url = RETRIEVE_DECISION_URL_TEMPLATE.format(session_id=session_id)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    response = requests.get(url, headers=headers)
    print("🔹 Recuperando decision para session_id:", session_id)
    print("🔹 Decision Response Status:", response.status_code)
    print("🔹 Decision Response:", response.text[:500])
    response.raise_for_status()
    return response.json()

def update_session_status(session_id, new_status, comment=None):
    access_token = get_client_token()
    if not access_token:
        raise Exception("Error fetching client token for update.")
    
    url = f"https://verification.didit.me/v1/session/{session_id}/update-status/"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    
    body = {
        "new_status": new_status
    }
    if comment:
        body["comment"] = comment

    response = requests.patch(url, headers=headers, json=body)
    print("🔹 Update Status Response Status:", response.status_code)
    print("🔹 Update Status Response:", response.text[:500])
    response.raise_for_status()
    return response.json()

