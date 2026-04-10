"""
escrow_engine.providers.selcom
-------------------------------
Selcom implementation of the BasePaymentProvider.
Handles multi-channel payments (M-Pesa, Tigo, Airtel, Card) and Qwiksend payouts.
"""
import os
import json
import base64
import hashlib
import hmac
import time
import requests
import logging
from decimal import Decimal
from django.conf import settings
from typing import TYPE_CHECKING, Optional
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

from escrow_engine.providers.base import BasePaymentProvider, PaymentResult
from escrow_engine.services.gateway_retry import call_with_gateway_retry

if TYPE_CHECKING:
    from escrow_engine.models import Transaction

logger = logging.getLogger(__name__)


class SelcomProvider(BasePaymentProvider):
    """
    Selcom aggregator integration.
    """

    def __init__(self):
        self.api_key = os.getenv('SELCOM_API_KEY', '')
        self.api_secret = os.getenv('SELCOM_API_SECRET', '')
        self.vendor_id = os.getenv('SELCOM_VENDOR_ID', '')
        
        # Determine environment
        is_production = os.getenv('DJANGO_ENV') == 'production'
        self.base_url = 'https://apigw.selcommobile.com/v1'

    def _generate_signature(self, payload: dict, timestamp: str) -> str:
        """Standard Selcom HMAC SHA256 signature."""
        data_string = json.dumps(payload, separators=(',', ':'))
        signed_data = f"{timestamp}{data_string}"
        
        return base64.b64encode(
            hashlib.hmac.new(
                self.api_secret.encode('utf-8'),
                signed_data.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')

    def _get_headers(self, payload: dict) -> dict:
        timestamp = str(int(time.time()))
        return {
            'Content-Type': 'application/json',
            'Authorization': f'SELCOM {self.api_key}',
            'Digest-Method': 'HS256',
            'Digest': self._generate_signature(payload, timestamp),
            'Timestamp': timestamp
        }

    def _request_post_json(self, url: str, payload: dict, *, operation: str) -> dict:
        """POST JSON with retries, 5s timeout per attempt, exponential backoff."""

        def _call():
            response = requests.post(
                url,
                json=payload,
                headers=self._get_headers(payload),
                timeout=5,
            )
            response.raise_for_status()
            return response.json()

        return call_with_gateway_retry(_call, operation=operation, retries=3)

    def initiate_payment(self, transaction: 'Transaction', **kwargs) -> PaymentResult:
        """
        Create a checkout order on Selcom Gateway.

        Hosted checkout supports card, mobile money pull, and bank rails; the buyer
        often chooses the final instrument on Selcom's page. We pass buyer-chosen
        `payment_channel` (card | mobile_money | bank) in remarks for reconciliation.

        kwargs:
          redirect_url, cancel_url — override defaults (pass frontend checkout URLs)
          buyer_phone, buyer_name — override display / MSISDN for mobile money
          payment_channel — logical choice from our checkout UI
        """
        url = f"{self.base_url}/checkout/create-order-minimal"

        buyer_name = (kwargs.get('buyer_name') or '').strip() or transaction.buyer_display
        buyer_phone = (
            (kwargs.get('buyer_phone') or '').strip()
            or transaction.buyer_phone
            or '255000000000'
        )

        payment_channel = (
            (kwargs.get('payment_channel') or '').strip()
            or (transaction.payment_method or 'selcom')
        )
        redirect_url = (
            kwargs.get('redirect_url')
            or f"{settings.FRONTEND_URL}/payment/success?ref={transaction.reference}"
        )
        cancel_url = (
            kwargs.get('cancel_url')
            or f"{settings.FRONTEND_URL}/payment/cancel?ref={transaction.reference}"
        )

        # Ensure the frontend always receives the engine transaction reference on return.
        # This allows marketplace checkout to confirm payment after redirect even when
        # webhooks are delayed/misconfigured.
        def _with_ref(u: str) -> str:
            if not u:
                return u
            try:
                parsed = urlparse(u)
                q = dict(parse_qsl(parsed.query, keep_blank_values=True))
                q.setdefault('ref', str(transaction.reference))
                return urlunparse(parsed._replace(query=urlencode(q)))
            except Exception:
                return u

        redirect_url = _with_ref(redirect_url)
        cancel_url = _with_ref(cancel_url)

        payload = {
            "vendor": self.vendor_id,
            "order_id": str(transaction.reference),
            "buyer_email": transaction.buyer_email or f"{transaction.reference}@smartdalali.local",
            "buyer_name": buyer_name,
            "buyer_phone": buyer_phone,
            "amount": float(transaction.amount),
            "currency": transaction.currency,
            "redirect_url": redirect_url,
            "cancel_url": cancel_url,
            "webhook_url": f"{settings.BACKEND_URL}/api/v1/escrow/webhooks/selcom/",
            "buyer_remarks": f"SmartDalali checkout — channel: {payment_channel}",
            "merchant_remarks": f"channel={payment_channel};order={transaction.reference}",
        }
        
        try:
            if not self.api_key:
                logger.warning("Selcom API keys missing. Simulating checkout.")
                return PaymentResult(
                    success=True,
                    payment_url=f"https://pay.selcommobile.com/mock/{transaction.reference}",
                    gateway_reference=f"MOCK_{transaction.reference}",
                    raw_payload={"mock": True}
                )

            data = self._request_post_json(url, payload, operation='selcom.initiate_payment')
            
            res_data = data.get('data', [{}])[0] if isinstance(data.get('data'), list) else data.get('data', {})
            
            return PaymentResult(
                success=data.get('result') == 'SUCCESS',
                payment_url=res_data.get('payment_gateway_url', ''),
                gateway_reference=res_data.get('reference', ''),
                raw_payload=data
            )
        except Exception as e:
            logger.error(f"Selcom initiate_payment failed: {str(e)}")
            return PaymentResult(success=False, error=str(e))

    def verify_webhook_signature(self, payload: str, signature: str, timestamp: str) -> bool:
        """
        Verify the HMAC signature of an inbound Selcom webhook.
        """
        if not self.api_secret or not signature:
            return False

        signed_data = f"{timestamp}{payload}"
        expected = base64.b64encode(
            hmac.new(
                self.api_secret.encode('utf-8'),
                signed_data.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')

        return hmac.compare_digest(signature, expected)

    def verify_payment(self, gateway_data: dict) -> PaymentResult:
        """
        Handle Selcom status check or webhook verification.
        """
        gateway_reference = gateway_data.get('reference') or gateway_data.get('transid')
        status = gateway_data.get('status')
        
        success = status in ['SUCCESS', 'COMPLETED', 'PAID']
        
        return PaymentResult(
            success=success,
            gateway_reference=gateway_reference,
            raw_payload=gateway_data
        )

    def query_payment_status(self, transaction: 'Transaction') -> PaymentResult:
        """
        Query Selcom checkout order status by marketplace order_id (engine reference).

        Uses POST /v1/checkout/order-status (vendor + order_id). If Selcom changes paths,
        update here only — commerce must never trust client-supplied payment status.
        """
        if not self.api_key or not self.vendor_id:
            return PaymentResult(
                success=False,
                error='selcom_not_configured_cannot_verify_payment_server_side',
                gateway_reference='',
                raw_payload={},
            )

        url = f"{self.base_url}/checkout/order-status"
        payload = {
            'vendor': self.vendor_id,
            'order_id': str(transaction.reference),
        }
        try:
            data = self._request_post_json(url, payload, operation='selcom.query_order_status')
        except Exception as e:
            logger.warning("Selcom order-status failed for %s: %s", transaction.reference, e)
            return PaymentResult(
                success=False,
                error=str(e),
                gateway_reference=transaction.gateway_reference or '',
                raw_payload={},
            )

        top_ok = data.get('result') == 'SUCCESS'
        block = data.get('data', data)
        if isinstance(block, list) and block:
            block = block[0]
        if not isinstance(block, dict):
            block = {}

        pay_status = (
            block.get('payment_status')
            or block.get('status')
            or data.get('payment_status')
            or data.get('status')
        )
        ps = str(pay_status or '').upper()
        paid = ps in ('SUCCESS', 'COMPLETED', 'PAID', 'SETTLED', 'COMPLETE')
        gateway_reference = (
            block.get('reference')
            or block.get('transid')
            or transaction.gateway_reference
            or ''
        )

        if top_ok and paid:
            return PaymentResult(
                success=True,
                gateway_reference=str(gateway_reference),
                raw_payload=data,
            )

        err = (data.get('message') or block.get('message') or 'payment_not_completed_or_pending')
        return PaymentResult(
            success=False,
            error=str(err)[:2000],
            gateway_reference=str(gateway_reference or ''),
            raw_payload=data,
        )

    def refund(self, transaction: 'Transaction', amount=None, reason: str = '') -> PaymentResult:
        """
        Selcom reversal API.
        """
        url = f"{self.base_url}/checkout/reverse-order"
        
        payload = {
            "vendor": self.vendor_id,
            "reference": transaction.gateway_reference,
            "amount": float(amount or transaction.amount),
            "reason": reason or "Refund requested"
        }
        
        try:
            if not self.api_key:
                return PaymentResult(success=True, gateway_reference=f"REFUND_{transaction.reference}")
                
            data = self._request_post_json(url, payload, operation='selcom.refund')
            
            return PaymentResult(
                success=data.get('result') == 'SUCCESS',
                gateway_reference=data.get('data', {}).get('reference'),
                raw_payload=data
            )
        except Exception as e:
            return PaymentResult(success=False, error=str(e))

    def disburse(
        self,
        transaction: 'Transaction',
        account_number: str,
        account_name: str,
        bank_code: str,
        *,
        amount: Optional[Decimal] = None,
    ) -> PaymentResult:
        """
        Selcom Qwiksend disbursement.
        """
        url = f"{self.base_url}/qwiksend/pull"

        pay_amount = amount if amount is not None else transaction.amount

        payload = {
            "vendor": self.vendor_id,
            "reference": f"OUT_{transaction.reference}",
            "amount": float(pay_amount),
            "currency": transaction.currency,
            "utility_code": bank_code,
            "utility_account": account_number,
            "account_name": account_name
        }
        
        try:
            if not self.api_key:
                return PaymentResult(success=True, gateway_reference=f"MOCK_DISB_{transaction.reference}")
                
            data = self._request_post_json(url, payload, operation='selcom.disburse')
            
            return PaymentResult(
                success=data.get('result') == 'SUCCESS',
                gateway_reference=data.get('data', {}).get('transaction_id'),
                raw_payload=data
            )
        except Exception as e:
            return PaymentResult(success=False, error=str(e))
