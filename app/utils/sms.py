"""SMS provider abstraction for OTP delivery.

Supported providers (set SMS_PROVIDER in .env):
- twilio:  Global, reliable. Env: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER
- msg91:   India-focused, DLT compliant. Env: MSG91_AUTH_KEY, MSG91_SENDER_ID
- fast2sms: Indian, affordable. Env: FAST2SMS_API_KEY
- mock:    Logs to console (dev). No credentials.
"""
import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


class SMSProvider(ABC):
    @abstractmethod
    def send_otp(self, phone: str, otp: str) -> bool:
        pass


class MockSMSProvider(SMSProvider):
    """Log OTP to console. Use for development."""

    def send_otp(self, phone: str, otp: str) -> bool:
        logger.info(f"[MOCK SMS] OTP for {phone}: {otp}")
        print(f"[MOCK SMS] OTP for {phone}: {otp}")  # noqa: T201
        return True


class TwilioSMSProvider(SMSProvider):
    """Twilio SMS. Global, reliable. https://www.twilio.com"""

    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        self._account_sid = account_sid
        self._auth_token = auth_token
        self._from_number = from_number

    def send_otp(self, phone: str, otp: str) -> bool:
        try:
            from twilio.rest import Client
            client = Client(self._account_sid, self._auth_token)
            client.messages.create(
                body=f"Your SHMS password reset OTP is: {otp}. Valid for 2 minutes.",
                from_=self._from_number,
                to=self._format_phone(phone)
            )
            return True
        except Exception as e:
            logger.error(f"Twilio send failed: {e}")
            return False

    def _format_phone(self, phone: str) -> str:
        p = phone.replace(" ", "").replace("-", "")
        return p if p.startswith("+") else f"+91{p}"  # assume India if no +


class MSG91SMSProvider(SMSProvider):
    """MSG91. India-focused, DLT compliant. https://msg91.com"""

    def __init__(self, auth_key: str, sender_id: str):
        self._auth_key = auth_key
        self._sender_id = sender_id

    def send_otp(self, phone: str, otp: str) -> bool:
        try:
            import urllib.request
            import json
            url = "https://api.msg91.com/api/v5/flow/"
            data = json.dumps({
                "template_id": "reset_otp",  # Configure in MSG91 dashboard
                "short_url": "0",
                "recipients": [{"mobiles": self._format_phone(phone), "otp": otp}]
            }).encode()
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "authkey": self._auth_key,
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"MSG91 send failed: {e}")
            return False

    def _format_phone(self, phone: str) -> str:
        p = phone.replace(" ", "").replace("-", "")
        return p[-10:] if len(p) >= 10 else p  # Indian 10-digit


class Fast2SMSSMSProvider(SMSProvider):
    """Fast2SMS. Indian, affordable. https://www.fast2sms.com"""

    def __init__(self, api_key: str):
        self._api_key = api_key

    def send_otp(self, phone: str, otp: str) -> bool:
        try:
            import urllib.request
            url = "https://www.fast2sms.com/dev/bulkV2"
            data = f"variables_values={otp}&route=otp&numbers={self._format_phone(phone)}".encode()
            req = urllib.request.Request(
                url,
                data=data,
                headers={"authorization": self._api_key},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"Fast2SMS send failed: {e}")
            return False

    def _format_phone(self, phone: str) -> str:
        p = phone.replace(" ", "").replace("-", "")
        return p[-10:] if len(p) >= 10 else p


def get_sms_provider(provider: str, **kwargs) -> SMSProvider:
    """Factory. provider: mock | twilio | msg91 | fast2sms"""
    if provider == "mock":
        return MockSMSProvider()
    if provider == "twilio":
        return TwilioSMSProvider(
            account_sid=kwargs.get("twilio_account_sid", ""),
            auth_token=kwargs.get("twilio_auth_token", ""),
            from_number=kwargs.get("twilio_phone", ""),
        )
    if provider == "msg91":
        return MSG91SMSProvider(
            auth_key=kwargs.get("msg91_auth_key", ""),
            sender_id=kwargs.get("msg91_sender_id", ""),
        )
    if provider == "fast2sms":
        return Fast2SMSSMSProvider(api_key=kwargs.get("fast2sms_api_key", ""))
    return MockSMSProvider()
