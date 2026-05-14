from backend.pii_redactor import redact_pii


class TestEmptyAndNoOp:
    def test_empty_string_unchanged(self):
        assert redact_pii("") == ""

    def test_plain_text_unchanged(self):
        text = "The quick brown fox jumps over the lazy dog."
        assert redact_pii(text) == text


class TestEmail:
    def test_single_email_redacted(self):
        result = redact_pii("Contact admin@example.com for help.")
        assert "[REDACTED_EMAIL]" in result
        assert "admin@example.com" not in result

    def test_multiple_emails_all_redacted(self):
        result = redact_pii("From a@b.com to c@d.org")
        assert result.count("[REDACTED_EMAIL]") == 2

    def test_email_with_subdomain(self):
        result = redact_pii("user@mail.example.co.uk")
        assert "[REDACTED_EMAIL]" in result


class TestPhone:
    def test_dash_separated(self):
        assert "[REDACTED_PHONE]" in redact_pii("Call 555-867-5309")

    def test_dot_separated(self):
        assert "[REDACTED_PHONE]" in redact_pii("Reach us at 555.867.5309")

    def test_space_separated(self):
        assert "[REDACTED_PHONE]" in redact_pii("Dial 555 867 5309")


class TestSSN:
    def test_ssn_pattern(self):
        assert "[REDACTED_SSN]" in redact_pii("SSN: 123-45-6789")

    def test_ssn_not_confused_with_phone(self):
        result = redact_pii("SSN 123-45-6789")
        assert "[REDACTED_SSN]" in result


class TestCreditCard:
    # Visa test number — passes Luhn check
    VALID_CARD = "4111111111111111"
    # Same digits rearranged — fails Luhn check
    INVALID_CARD = "4111111111111112"

    def test_valid_card_redacted(self):
        result = redact_pii(f"Card: {self.VALID_CARD}")
        assert "[REDACTED_CARD]" in result
        assert self.VALID_CARD not in result

    def test_invalid_card_not_redacted(self):
        result = redact_pii(f"Number: {self.INVALID_CARD}")
        assert "[REDACTED_CARD]" not in result

    def test_mastercard_test_number(self):
        # 5500005555555559 passes Luhn
        result = redact_pii("MC: 5500005555555559")
        assert "[REDACTED_CARD]" in result


class TestMultiplePiiTypes:
    def test_mixed_pii_all_redacted(self):
        text = "Email admin@corp.com, SSN 123-45-6789, card 4111111111111111"
        result = redact_pii(text)
        assert "[REDACTED_EMAIL]" in result
        assert "[REDACTED_SSN]" in result
        assert "[REDACTED_CARD]" in result
        assert "admin@corp.com" not in result
        assert "123-45-6789" not in result
        assert "4111111111111111" not in result
