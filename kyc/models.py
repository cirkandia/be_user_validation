from django.db import models

class UserDetails(models.Model):
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255, default="")
    document_id = models.CharField(max_length=100)
    document_type = models.CharField(max_length=50, default="unknown")  # Nuevo campo para el tipo de documento
    nationality = models.CharField(max_length=100, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.document_id}"

class SessionDetails(models.Model):
    personal_data = models.OneToOneField(UserDetails, on_delete=models.CASCADE, related_name='session_details')
    session_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    status = models.CharField(max_length=50, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Session {self.session_id} - {self.status}"
