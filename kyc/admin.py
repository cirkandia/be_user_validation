from django.contrib import admin
from .models import KYCRequest

@admin.register(KYCRequest)
class KYCRequestAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'document_id', 'session_id', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('full_name', 'document_id', 'session_id')
