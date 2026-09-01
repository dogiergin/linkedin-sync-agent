import time
import requests
from typing import Dict, Any, Tuple
from loguru import logger
from src.config import config


class WebhookDispatcher:
    """Dispatches extracted LinkedIn post data to the destination webhook."""

    def __init__(
        self,
        webhook_url: str = config.webhook_url,
        webhook_secret: str = config.webhook_secret,
        max_retries: int = config.max_retries,
        retry_delay: int = config.retry_delay_seconds,
    ):
        self.webhook_url = webhook_url
        self.webhook_secret = webhook_secret
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def send(self, payload: Dict[str, Any]) -> Tuple[bool, int, str]:
        """
        Sends payload to the webhook endpoint with retries and exponential backoff.
        
        Returns:
            Tuple[bool, int, str]: (is_success, status_code, response_text)
        """
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "LinkedInSyncAgent/1.0 (+https://dogukanergin.com)",
        }

        if self.webhook_secret:
            headers["Authorization"] = f"Bearer {self.webhook_secret}"
            headers["X-Webhook-Secret"] = self.webhook_secret

        logger.info(f"Sending webhook to {self.webhook_url}...")
        logger.debug(f"Payload: {payload}")

        delay = self.retry_delay

        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.post(
                    self.webhook_url,
                    json=payload,
                    headers=headers,
                    timeout=15,
                )

                if 200 <= response.status_code < 300:
                    logger.info(f"Webhook delivered successfully! Status: {response.status_code}")
                    return True, response.status_code, response.text
                elif 400 <= response.status_code < 500:
                    # Client error (4xx) - usually no point in retrying without fixing payload/url
                    logger.error(f"Client error on webhook ({response.status_code}): {response.text}")
                    return False, response.status_code, response.text
                else:
                    # Server error (5xx)
                    logger.warning(
                        f"Server error on attempt {attempt}/{self.max_retries} "
                        f"({response.status_code}): {response.text}. Retrying in {delay}s..."
                    )

            except requests.exceptions.RequestException as e:
                logger.warning(
                    f"Network error on attempt {attempt}/{self.max_retries}: {e}. "
                    f"Retrying in {delay}s..."
                )

            if attempt < self.max_retries:
                time.sleep(delay)
                delay *= 2  # Exponential backoff

        logger.error(f"Failed to deliver webhook after {self.max_retries} attempts.")
        return False, 0, "Max retries exceeded"
