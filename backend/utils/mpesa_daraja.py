"""
M-Pesa Daraja API Integration

This module implements secure M-Pesa payment integration using
Safaricom's official Daraja API. All security relies on Safaricom's
official endpoints and authentication mechanisms.

Documentation: https://developer.safaricom.co.ke/
"""
import base64
import logging
from datetime import datetime
from typing import Dict, Optional

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Safaricom Daraja API endpoints
# Production: https://api.safaricom.co.ke
# Sandbox: https://sandbox.safaricom.co.ke
MPESA_API_BASE = getattr(
    settings, 'MPESA_API_BASE', 'https://sandbox.safaricom.co.ke'
)
MPESA_OAUTH_URL = (
    f'{MPESA_API_BASE}/oauth/v1/generate?grant_type=client_credentials'
)
MPESA_STK_PUSH_URL = (
    f'{MPESA_API_BASE}/mpesa/stkpush/v1/processrequest'
)
MPESA_QUERY_URL = (
    f'{MPESA_API_BASE}/mpesa/stkpushquery/v1/query'
)
MPESA_B2C_PAYOUT_URL = (
    f'{MPESA_API_BASE}/mpesa/b2c/v1/paymentrequest'
)


class MpesaDarajaError(Exception):
    """Base exception for M-Pesa Daraja API errors"""


class MpesaDarajaService:
    """
    M-Pesa Daraja API Service
    
    Handles all interactions with Safaricom's Daraja API including:
    - OAuth token generation
    - STK Push requests
    - Payment status queries
    - Callback validation
    
    All security relies on Safaricom's official endpoints and authentication.
    """

    def __init__(self):
        self.consumer_key = getattr(settings, 'DAR_AFFILIATE_CONSUMER_KEY', None)
        self.consumer_secret = getattr(settings, 'DAR_AFFILIATE_CONSUMER_SECRET', None)
        self.business_shortcode = getattr(settings, 'DAR_SHORTCODE', None)
        self.passkey = getattr(settings, 'DAR_PASSKEY', None)
        self.callback_url = getattr(settings, 'MPESA_CALLBACK_URL', None)
        
        # B2C specific settings
        self.initiator_name = getattr(settings, 'DAR_B2C_INITIATOR_NAME', None)
        self.security_credential = getattr(settings, 'DAR_B2C_SECURITY_CREDENTIAL', None)
        self.b2c_shortcode = getattr(settings, 'DAR_B2C_SHORTCODE', self.business_shortcode)
        self.b2c_result_url = getattr(settings, 'MPESA_B2C_RESULT_URL', self.callback_url)
        self.b2c_timeout_url = getattr(settings, 'MPESA_B2C_TIMEOUT_URL', self.callback_url)
        
        if not all([self.consumer_key, self.consumer_secret, self.business_shortcode, self.passkey]):
            logger.warning("M-Pesa Daraja credentials not fully configured")
        
        self._access_token = None
        self._token_expires_at = None

    def _get_access_token(self) -> str:
        """
        Get OAuth access token from Safaricom.
        
        Uses Basic Authentication as per Safaricom's security requirements.
        Token is cached until expiration.
        
        Returns:
            str: Access token for API requests
            
        Raises:
            MpesaDarajaError: If authentication fails
        """
        # Return cached token if still valid (with 5 minute buffer)
        if self._access_token and self._token_expires_at:
            if timezone.now() < self._token_expires_at:
                return self._access_token
        
        if not self.consumer_key or not self.consumer_secret:
            raise MpesaDarajaError("M-Pesa consumer key and secret must be configured")
        
        try:
            # Create Basic Auth header as per Safaricom documentation
            auth_string = f"{self.consumer_key}:{self.consumer_secret}"
            auth_bytes = auth_string.encode('ascii')
            auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
            
            headers = {
                'Authorization': f'Basic {auth_b64}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                MPESA_OAUTH_URL,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            access_token = data.get('access_token')
            expires_in = data.get('expires_in', 3599)  # Default 1 hour
            
            if not access_token:
                raise MpesaDarajaError("No access token received from Safaricom")
            
            # Cache token
            self._access_token = access_token
            self._token_expires_at = timezone.now().replace(microsecond=0) + timezone.timedelta(seconds=expires_in - 300)  # 5 min buffer
            
            logger.info("M-Pesa access token obtained successfully")
            return access_token
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get M-Pesa access token: {e}")
            raise MpesaDarajaError(f"Failed to authenticate with Safaricom: {str(e)}")
        except (KeyError, ValueError) as e:
            logger.error(f"Invalid response from Safaricom OAuth: {e}")
            raise MpesaDarajaError(f"Invalid response from Safaricom: {str(e)}")

    def _generate_password(self, timestamp: str) -> str:
        """
        Generate password for STK Push as per Safaricom documentation.
        
        Password = Base64(BusinessShortCode + Passkey + Timestamp)
        
        Args:
            timestamp: Current timestamp in format YYYYMMDDHHmmss
            
        Returns:
            str: Base64 encoded password
        """
        if not self.business_shortcode or not self.passkey:
            raise MpesaDarajaError("Business shortcode and passkey must be configured")
        
        password_string = f"{self.business_shortcode}{self.passkey}{timestamp}"
        password_bytes = password_string.encode('ascii')
        password_b64 = base64.b64encode(password_bytes).decode('ascii')
        
        return password_b64

    def _normalize_phone_number(self, phone: str) -> str:
        """
        Normalize phone number to Safaricom format (254XXXXXXXXX).
        
        Args:
            phone: Phone number in various formats
            
        Returns:
            str: Normalized phone number (254XXXXXXXXX)
        """
        # Remove all non-digit characters
        digits = ''.join(filter(str.isdigit, phone))
        
        # Handle different formats
        if digits.startswith('0'):
            # 0712345678 -> 254712345678
            return '254' + digits[1:]
        elif digits.startswith('254'):
            # Already in correct format
            return digits
        elif digits.startswith('+254'):
            # +254712345678 -> 254712345678
            return digits[1:]
        else:
            # Assume it's a 9-digit number starting with 7
            return '254' + digits

    def initiate_stk_push(
        self,
        phone_number: str,
        amount: float,
        account_reference: str,
        transaction_description: str,
        callback_url: str
    ) -> Dict:
        """
        Initiate STK Push payment request.
        
        This sends a push notification to the customer's phone to enter their M-Pesa PIN.
        Security is handled entirely by Safaricom - we only initiate the request.
        
        Args:
            phone_number: Customer's M-Pesa registered phone number
            amount: Payment amount (KES)
            account_reference: Unique reference for this transaction
            transaction_description: Description shown to customer
            callback_url: URL where Safaricom will send payment result
            
        Returns:
            dict: Response from Safaricom containing CheckoutRequestID
            
        Raises:
            MpesaDarajaError: If request fails
        """
        if not all([self.business_shortcode, self.passkey, self.consumer_key, self.consumer_secret]):
            raise MpesaDarajaError("M-Pesa credentials not fully configured")
        
        try:
            # Get access token
            access_token = self._get_access_token()
            
            # Generate timestamp and password
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password = self._generate_password(timestamp)
            
            # Normalize phone number
            normalized_phone = self._normalize_phone_number(phone_number)
            
            # Prepare STK Push payload as per Safaricom documentation
            payload = {
                "BusinessShortCode": self.business_shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": int(amount),  # Safaricom expects integer (KES)
                "PartyA": normalized_phone,
                "PartyB": self.business_shortcode,
                "PhoneNumber": normalized_phone,
                "CallBackURL": callback_url,
                "AccountReference": account_reference,
                "TransactionDesc": transaction_description
            }
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            logger.info(f"Initiating STK Push: {account_reference}, Amount: {amount}, Phone: {normalized_phone}")
            
            response = requests.post(
                MPESA_STK_PUSH_URL,
                json=payload,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Check for errors in response
            if 'errorCode' in data:
                error_msg = data.get('errorMessage', 'Unknown error')
                logger.error(f"STK Push failed: {error_msg}")
                raise MpesaDarajaError(f"Safaricom error: {error_msg}")
            
            # Log successful initiation
            checkout_request_id = data.get('CheckoutRequestID')
            response_code = data.get('ResponseCode')
            customer_message = data.get('CustomerMessage', '')
            
            if response_code != '0':
                error_msg = data.get('errorMessage', f'Response code: {response_code}')
                logger.error(f"STK Push rejected: {error_msg}")
                raise MpesaDarajaError(f"STK Push rejected: {error_msg}")
            
            logger.info(f"STK Push initiated successfully. CheckoutRequestID: {checkout_request_id}")
            
            return {
                'CheckoutRequestID': checkout_request_id,
                'ResponseCode': response_code,
                'ResponseDescription': data.get('ResponseDescription', ''),
                'CustomerMessage': customer_message,
                'MerchantRequestID': data.get('MerchantRequestID', '')
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during STK Push: {e}")
            raise MpesaDarajaError(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during STK Push: {e}")
            raise MpesaDarajaError(f"Unexpected error: {str(e)}")

    def initiate_b2c_payout(
        self,
        phone_number: str,
        amount: float,
        remarks: str,
        occasion: str = "Payout",
        command_id: str = "BusinessPayment"
    ) -> Dict:
        """
        Initiate B2C (Business to Customer) payout.
        
        Args:
            phone_number: Recipient's M-Pesa phone number
            amount: Payout amount (KES)
            remarks: Remarks for the payout
            occasion: Occasion for the payout
            command_id: Command ID (BusinessPayment, SalaryPayment, PromotionPayment)
            
        Returns:
            dict: response from Safaricom
        """
        if not all([self.initiator_name, self.security_credential, self.b2c_shortcode]):
             logger.warning("M-Pesa B2C credentials not fully configured. Payout might fail.")
             # For now, we'll allow it to proceed and let the API return an error if truly missing
        
        try:
            access_token = self._get_access_token()
            normalized_phone = self._normalize_phone_number(phone_number)
            
            payload = {
                "InitiatorName": self.initiator_name or "Manager",
                "SecurityCredential": self.security_credential or "encrypted_credential",
                "CommandID": command_id,
                "Amount": int(amount),
                "PartyA": self.b2c_shortcode,
                "PartyB": normalized_phone,
                "Remarks": remarks[:100],
                "QueueTimeOutURL": self.b2c_timeout_url,
                "ResultURL": self.b2c_result_url,
                "Occassion": occasion[:100]
            }
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            logger.info(f"Initiating B2C Payout: {normalized_phone}, Amount: {amount}")
            
            response = requests.post(
                MPESA_B2C_PAYOUT_URL,
                json=payload,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Error during B2C Payout: {e}")
            raise MpesaDarajaError(f"B2C Payout failed: {str(e)}")

    def query_payment_status(self, checkout_request_id: str) -> Dict:
        """
        Query payment status from Safaricom.
        
        Args:
            checkout_request_id: The CheckoutRequestID from STK Push
            
        Returns:
            dict: Payment status information from Safaricom
            
        Raises:
            MpesaDarajaError: If query fails
        """
        if not all([self.business_shortcode, self.passkey]):
            raise MpesaDarajaError("M-Pesa credentials not fully configured")
        
        try:
            access_token = self._get_access_token()
            
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password = self._generate_password(timestamp)
            
            payload = {
                "BusinessShortCode": self.business_shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "CheckoutRequestID": checkout_request_id
            }
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                MPESA_QUERY_URL,
                json=payload,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during payment status query: {e}")
            raise MpesaDarajaError(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during payment status query: {e}")
            raise MpesaDarajaError(f"Unexpected error: {str(e)}")

    @staticmethod
    def validate_callback_payload(payload: Dict) -> bool:
        """
        Validate callback payload structure.
        
        Safaricom sends callbacks with a specific structure. This validates
        that the payload matches the expected format.
        
        Args:
            payload: Callback payload from Safaricom
            
        Returns:
            bool: True if payload structure is valid
        """
        try:
            # Check for required top-level keys
            if 'Body' not in payload:
                logger.warning("Callback payload missing 'Body' key")
                return False
            
            body = payload['Body']
            if 'stkCallback' not in body:
                logger.warning("Callback payload missing 'stkCallback' key")
                return False
            
            stk_callback = body['stkCallback']
            
            # Check for required callback fields
            required_fields = ['CheckoutRequestID', 'ResultCode', 'ResultDesc']
            for field in required_fields:
                if field not in stk_callback:
                    logger.warning(f"Callback payload missing required field: {field}")
                    return False
            
            return True
            
        except (TypeError, AttributeError) as e:
            logger.error(f"Error validating callback payload: {e}")
            return False

    @staticmethod
    def extract_callback_data(payload: Dict) -> Optional[Dict]:
        """
        Extract relevant data from Safaricom callback payload.
        
        Args:
            payload: Callback payload from Safaricom
            
        Returns:
            dict: Extracted callback data or None if invalid
        """
        if not MpesaDarajaService.validate_callback_payload(payload):
            return None
        
        try:
            stk_callback = payload['Body']['stkCallback']
            callback_items = stk_callback.get('CallbackMetadata', {}).get('Item', [])
            
            # Extract callback metadata
            callback_data = {}
            for item in callback_items:
                name = item.get('Name')
                value = item.get('Value')
                if name and value is not None:
                    callback_data[name] = value
            
            return {
                'CheckoutRequestID': stk_callback.get('CheckoutRequestID'),
                'MerchantRequestID': stk_callback.get('MerchantRequestID'),
                'ResultCode': stk_callback.get('ResultCode'),
                'ResultDesc': stk_callback.get('ResultDesc'),
                'Amount': callback_data.get('Amount'),
                'MpesaReceiptNumber': callback_data.get('MpesaReceiptNumber'),
                'TransactionDate': callback_data.get('TransactionDate'),
                'PhoneNumber': callback_data.get('PhoneNumber'),
            }
            
        except (TypeError, AttributeError, KeyError) as e:
            logger.error(f"Error extracting callback data: {e}")
            return None


# Singleton instance
_mpesa_service = None


def get_mpesa_service() -> MpesaDarajaService:
    """Get singleton M-Pesa Daraja service instance."""
    global _mpesa_service
    if _mpesa_service is None:
        _mpesa_service = MpesaDarajaService()
    return _mpesa_service

