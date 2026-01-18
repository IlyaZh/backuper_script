from abc import ABC, abstractmethod
import config
import os
import requests

class Notifier(ABC):
    @abstractmethod
    def send_success(self, archive_name: str, file_size_mb: float) -> None:
        pass

    @abstractmethod
    def send_error(self, error_message: str) -> None:  
        pass

class TelegramNotifier(Notifier):
    def __init__(self, cfg: config.TelegramConfig):
        self._config = cfg
        self._token = os.environ.get("TELEGRAM_BOT_TOKEN")

    def send_success(self, archive_name: str, file_size_mb: float) -> None:
        if not self._should_send():
            return

        message = (
            f"✅ <b>Backup Successful!</b>\n\n"
            f"📦 <b>File:</b> {archive_name}\n"
            f"💾 <b>Size:</b> {file_size_mb:.2f} MB\n"
            f"☁️ <b>Storage:</b> Cloudflare R2"
        )
        self._send(message)

    def send_error(self, error_message: str) -> None:
        if not self._should_send():
            return

        message = (
            f"❌ <b>Backup Failed!</b>\n\n"
            f"⚠️ <b>Error:</b>\n<pre>{error_message}</pre>"
        )
        self._send(message)

    def _should_send(self) -> bool:
        if not self._config.enabled:
            return False
        if not self._token:
            print("Warning: Telegram enabled in config, but TELEGRAM_BOT_TOKEN is missing.")
            return False
        return True

    def _send(self, text: str):
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        payload = {
            "chat_id": self._config.chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            print("Telegram: Notification sent.")
        except Exception as e:
            print(f"Telegram Error: Failed to send message. {e}")