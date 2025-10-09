"""Guardrails for PII scrubbing and output safety."""
import re
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class Guardrails:
    """
    Implement guardrails for AI system:
    - PII detection and redaction
    - Output validation
    - Sensitive data handling
    """

    # Common Brazilian PII patterns
    CPF_PATTERN = r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b'
    RG_PATTERN = r'\b\d{1,2}\.?\d{3}\.?\d{3}-?[0-9Xx]\b'
    PHONE_PATTERN = r'\b(?:\+55\s?)?(?:\(?\d{2}\)?\s?)?\d{4,5}-?\d{4}\b'
    EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    CREDIT_CARD_PATTERN = r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'

    # Sensitive keywords that might indicate PII
    SENSITIVE_KEYWORDS = [
        'senha', 'password', 'token', 'secret', 'api_key',
        'credit_card', 'cartao', 'cpf', 'rg', 'passaporte'
    ]

    @staticmethod
    def scrub_pii(text: str) -> str:
        """
        Remove PII from text using regex patterns.

        This is a deterministic, zero-latency approach that doesn't
        require additional LLM calls.
        """
        if not text:
            return text

        scrubbed = text

        # Redact CPF
        scrubbed = re.sub(
            Guardrails.CPF_PATTERN,
            '[CPF_REDACTED]',
            scrubbed
        )

        # Redact RG
        scrubbed = re.sub(
            Guardrails.RG_PATTERN,
            '[RG_REDACTED]',
            scrubbed
        )

        # Redact phone numbers
        scrubbed = re.sub(
            Guardrails.PHONE_PATTERN,
            '[PHONE_REDACTED]',
            scrubbed
        )

        # Redact email addresses
        scrubbed = re.sub(
            Guardrails.EMAIL_PATTERN,
            '[EMAIL_REDACTED]',
            scrubbed
        )

        # Redact credit cards
        scrubbed = re.sub(
            Guardrails.CREDIT_CARD_PATTERN,
            '[CREDIT_CARD_REDACTED]',
            scrubbed
        )

        return scrubbed

    @staticmethod
    def contains_pii(text: str) -> bool:
        """Check if text contains potential PII."""
        if not text:
            return False

        patterns = [
            Guardrails.CPF_PATTERN,
            Guardrails.RG_PATTERN,
            Guardrails.PHONE_PATTERN,
            Guardrails.EMAIL_PATTERN,
            Guardrails.CREDIT_CARD_PATTERN,
        ]

        for pattern in patterns:
            if re.search(pattern, text):
                return True

        return False

    @staticmethod
    def validate_output(output: str, max_length: int = 1000000) -> Dict[str, Any]:
        """
        Validate LLM output for safety and quality.

        Returns:
            {
                'valid': bool,
                'issues': list of strings,
                'scrubbed_output': str (PII removed)
            }
        """
        issues = []

        # Check length
        if len(output) > max_length:
            issues.append(f"Output too long ({len(output)} > {max_length} chars)")

        # Check for PII
        if Guardrails.contains_pii(output):
            issues.append("Output contains potential PII")

        # Check for sensitive keywords
        output_lower = output.lower()
        found_keywords = [
            kw for kw in Guardrails.SENSITIVE_KEYWORDS
            if kw in output_lower
        ]
        if found_keywords:
            issues.append(f"Contains sensitive keywords: {found_keywords}")

        # Scrub PII regardless
        scrubbed = Guardrails.scrub_pii(output)

        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'scrubbed_output': scrubbed,
        }

    @staticmethod
    def sanitize_user_input(user_input: str) -> str:
        """
        Sanitize user input before processing.

        - Remove potential injection attempts
        - Limit length
        - Remove special characters that could break queries
        """
        if not user_input:
            return ""

        # Limit length
        sanitized = user_input[:1000]

        # Remove potential SQL injection patterns (basic)
        dangerous_patterns = [
            r';\s*DROP',
            r';\s*DELETE',
            r';\s*UPDATE',
            r'--',
            r'/\*',
            r'\*/',
            r'xp_',
            r'sp_',
        ]

        for pattern in dangerous_patterns:
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)

        return sanitized

    @staticmethod
    def apply_output_schema(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply schema constraints to output data.

        Ensures output conforms to expected structure.
        """
        # Define expected schema
        expected_keys = [
            'report', 'metrics', 'chart_data',
            'news_citations', 'audit_trail'
        ]

        # Filter to only expected keys
        filtered = {
            k: v for k, v in data.items()
            if k in expected_keys
        }

        # Ensure required keys exist
        for key in ['report', 'metrics']:
            if key not in filtered:
                filtered[key] = None

        return filtered

    @staticmethod
    def log_security_event(event_type: str, details: str):
        """Log security-relevant events for audit."""
        logger.warning(f"SECURITY EVENT [{event_type}]: {details}")


# Convenience functions
def scrub_pii(text: str) -> str:
    """Convenience function to scrub PII from text."""
    return Guardrails.scrub_pii(text)


def validate_output(output: str) -> Dict[str, Any]:
    """Convenience function to validate output."""
    return Guardrails.validate_output(output)


def sanitize_input(user_input: str) -> str:
    """Convenience function to sanitize user input."""
    return Guardrails.sanitize_user_input(user_input)


def apply_output_schema(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function to apply output schema."""
    return Guardrails.apply_output_schema(data)


def log_security_event(event_type: str, details: str):
    """Convenience function to log security events."""
    return Guardrails.log_security_event(event_type, details)
