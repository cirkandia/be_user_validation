from django.contrib import admin
from .models import UserDetails, SessionDetails

@admin.register(UserDetails)
class UserDetailsAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'document_id', 'document_type', 'nationality', 'date_of_birth')
    search_fields = ('first_name', 'last_name', 'document_id')

@admin.register(SessionDetails)
class SessionDetailsAdmin(admin.ModelAdmin):
    list_display = ('session_id', 'status', 'created_at', 'updated_at', 'personal_data')
    list_filter = ('status', 'created_at')
    search_fields = ('session_id', 'personal_data__first_name', 'personal_data__last_name', 'personal_data__document_id')
