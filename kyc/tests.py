import pytest
from django.db import IntegrityError
from datetime import datetime
from django.utils import timezone
from .models import KYCRequest

@pytest.mark.django_db
class TestKYCRequest:

    def test_create_kyc_request(self):
        """Test creating a KYC request with valid data."""
        kyc_request = KYCRequest.objects.create(
            full_name="John Doe",
            document_id="1234567890",
            session_id="test-session-123"
        )
        assert kyc_request.id is not None
        assert kyc_request.full_name == "John Doe"
        assert kyc_request.document_id == "1234567890"
        assert kyc_request.session_id == "test-session-123"
        
    def test_default_status(self):
        """Test default status is 'pending'."""
        kyc_request = KYCRequest.objects.create(
            full_name="Jane Smith",
            document_id="9876543210"
        )
        assert kyc_request.status == 'pending'
        
    def test_string_representation(self):
        """Test the string representation of the model."""
        kyc_request = KYCRequest.objects.create(
            full_name="Alice Johnson",
            document_id="ABCD1234"
        )
        expected = f"{kyc_request.full_name} - {kyc_request.document_id}"
        # Note: This assumes you might want to add a __str__ method to your model
        # If you haven't implemented __str__, this test will fail
        assert str(kyc_request) == expected
        
    def test_session_id_unique(self):
        """Test session_id uniqueness constraint."""
        KYCRequest.objects.create(
            full_name="Bob Williams",
            document_id="XYZ9876",
            session_id="unique-session-id"
        )
        
        # Attempting to create another request with the same session_id should fail
        with pytest.raises(IntegrityError):
            KYCRequest.objects.create(
                full_name="Charlie Brown",
                document_id="ABC1234",
                session_id="unique-session-id"
            )
            
    def test_created_updated_timestamps(self):
        """Test that timestamps are set correctly."""
        before_creation = timezone.now()
        kyc_request = KYCRequest.objects.create(
            full_name="David Miller",
            document_id="QWERTY123"
        )
        after_creation = timezone.now()
        
        # Check timestamps are between before and after creation time
        assert before_creation <= kyc_request.created_at <= after_creation
        assert before_creation <= kyc_request.updated_at <= after_creation
        
    def test_status_choices(self):
        """Test status choices are enforced."""
        kyc_request = KYCRequest.objects.create(
            full_name="Eva Green",
            document_id="ZXCVB987",
            status='approved'
        )
        assert kyc_request.status == 'approved'
        
        kyc_request.status = 'rejected'
        kyc_request.save()
        assert kyc_request.status == 'rejected'