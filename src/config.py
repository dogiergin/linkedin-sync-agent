import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ConfigDict

# Load .env file from project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")


class AppConfig(BaseModel):
    """Application configuration schema."""

    # Project Directories
    base_dir: Path = BASE_DIR
    data_dir: Path = BASE_DIR / "data"
    logs_dir: Path = BASE_DIR / "logs"

    # LinkedIn Settings
    linkedin_activity_url: str = Field(
        default_factory=lambda: os.getenv(
            "LINKEDIN_ACTIVITY_URL",
            "https://www.linkedin.com/in/dogukanergin/recent-activity/all/",
        )
    )
    linkedin_li_at: str = Field(
        default_factory=lambda: os.getenv("LINKEDIN_LI_AT", "")
    )
    session_file: Path = Field(
        default_factory=lambda: BASE_DIR
        / os.getenv("SESSION_FILE", "data/session.json")
    )
    state_file: Path = Field(
        default_factory=lambda: BASE_DIR / "data/last_sync.json"
    )

    # Webhook Settings
    webhook_url: str = Field(
        default_factory=lambda: os.getenv(
            "WEBHOOK_URL", "https://dogukanergin.com/api/linkedin-webhook"
        )
    )
    webhook_secret: str = Field(
        default_factory=lambda: os.getenv("WEBHOOK_SECRET", "")
    )

    # Browser & Execution Settings
    headless: bool = Field(
        default_factory=lambda: os.getenv("HEADLESS", "true").lower()
        in ("1", "true", "yes")
    )
    sync_schedule_time: str = Field(
        default_factory=lambda: os.getenv("SYNC_SCHEDULE_TIME", "09:00")
    )
    max_retries: int = Field(
        default_factory=lambda: int(os.getenv("MAX_RETRIES", "3"))
    )
    retry_delay_seconds: int = Field(
        default_factory=lambda: int(os.getenv("RETRY_DELAY_SECONDS", "5"))
    )
    page_timeout_ms: int = Field(
        default_factory=lambda: int(os.getenv("PAGE_TIMEOUT_MS", "45000"))
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)


# Global settings instance
config = AppConfig()
