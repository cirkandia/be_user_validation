from django.db import models

class KYCRequest(models.Model):
    full_name = models.CharField(max_length=255)
    document_id = models.CharField(max_length=100)
    session_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    status = models.CharField(max_length=50, default="pending")
    vendor_data = models.TextField(null=True, blank=True)  # opcional, si quieres guardar info adicional
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.full_name} - {self.document_id} - {self.status}"
