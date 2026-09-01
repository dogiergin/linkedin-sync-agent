import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger
from src.config import config


class StateManager:
    """Manages tracking of synced posts to avoid duplicate webhook dispatches."""

    def __init__(self, state_file: Optional[Path] = None):
        self.state_file = state_file or config.state_file
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        """Loads state data from the JSON state file."""
        if not self.state_file.exists():
            return {}
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read state file ({self.state_file}): {e}. Starting with empty state.")
            return {}

    def _save(self) -> None:
        """Persists current state to the JSON state file."""
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save state file ({self.state_file}): {e}")

    @staticmethod
    def compute_content_hash(content: str) -> str:
        """Computes a SHA256 hash of the content string."""
        return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()

    def is_already_synced(self, post_url: str, post_content: str) -> bool:
        """
        Checks if a post has already been synced based on its URL or content hash.
        """
        last_url = self._state.get("last_url", "")
        last_hash = self._state.get("last_content_hash", "")

        content_hash = self.compute_content_hash(post_content)

        # Check URL match (if available and clean)
        if post_url and last_url and post_url.strip() == last_url.strip():
            return True

        # Check content hash match
        if content_hash and last_hash and content_hash == last_hash:
            return True

        return False

    def record_sync(self, post_data: Dict[str, Any]) -> None:
        """Records a successful sync in the state file."""
        content = post_data.get("content", "")
        self._state = {
            "last_url": post_data.get("url", ""),
            "last_content_hash": self.compute_content_hash(content),
            "last_post_date": post_data.get("date", ""),
            "last_hashtags": post_data.get("hashtags", []),
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save()
        logger.info(f"Updated sync state with post URL: {self._state['last_url']}")

    def get_last_sync_info(self) -> Dict[str, Any]:
        """Returns the last sync state details."""
        return self._state.copy()
