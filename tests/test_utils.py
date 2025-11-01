from src.core.utils import mask_pii


# ============================================================================
# PII MASKING TESTS
# ============================================================================

class TestPIIMasking:
    """Tests for PII detection and masking"""
    
    def test_mask_email(self):
        """Test email masking"""
        text = "Contact us at support@hospital.com for assistance."
        masked = mask_pii(text)
        
        assert "[EMAIL]" in masked
        assert "support@hospital.com" not in masked
    
    def test_mask_phone_number(self):
        """Test phone number masking"""
        text = "Call 555-123-4567 or 555.987.6543 for help."
        masked = mask_pii(text)
        
        assert "[PHONE]" in masked
        assert "555-123-4567" not in masked
        assert "555.987.6543" not in masked
    
    def test_mask_credit_card(self):
        """Test credit card masking"""
        text = "Card number: 1234-5678-9012-3456"
        masked = mask_pii(text)
        
        assert "[CREDIT_CARD]" in masked
        assert "1234-5678-9012-3456" not in masked
    
    def test_mask_ssn(self):
        """Test SSN masking"""
        text = "SSN: 123-45-6789"
        masked = mask_pii(text)
        
        assert "[SSN]" in masked
        assert "123-45-6789" not in masked
    
    def test_mask_multiple_pii(self):
        """Test masking multiple PII types"""
        text = "Contact John at john@email.com or 555-1234. SSN: 123-45-6789"
        masked = mask_pii(text)
        
        assert "[EMAIL]" in masked
        assert "[PHONE]" in masked
        assert "[SSN]" in masked
        assert "john@email.com" not in masked
        assert "555-1234" not in masked
    
    def test_mask_preserves_non_pii(self):
        """Test that non-PII text is preserved"""
        text = "The patient presented with symptoms of fever and cough."
        masked = mask_pii(text)
        
        assert masked == text, "Non-PII text should be unchanged"

