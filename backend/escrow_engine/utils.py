"""Utility functions for escrow_engine"""

def scrub_gateway_payload(payload: dict) -> dict:
    """
    Redact PII from gateway responses before storage.
    
    Removes or masks sensitive keys from any dictionary (and recursively in child dicts).
    """
    if not isinstance(payload, dict):
        return payload
        
    sensitive_keys = {
        'msisdn', 'phone', 'phone_number', 'customer_phone',
        'account_number', 'card_number', 'cvv'
    }
    
    scrubbed = {}
    for k, v in payload.items():
        if k.lower() in sensitive_keys:
            scrubbed[k] = "***REDACTED***"
        elif isinstance(v, dict):
            scrubbed[k] = scrub_gateway_payload(v)
        elif isinstance(v, list):
            scrubbed[k] = [
                scrub_gateway_payload(item) if isinstance(item, dict) else item
                for item in v
            ]
        else:
            scrubbed[k] = v
    return scrubbed
