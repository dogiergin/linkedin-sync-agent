import io
import sys
import time
import argparse
from pathlib import Path
from typing import Optional

# Reconfigure standard output encoding to UTF-8 for Windows console compatibility
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint

from src.config import config
from src.scraper import LinkedInScraper
from src.webhook import WebhookDispatcher
from src.state_manager import StateManager
from src.extractor import PostExtractor

console = Console(legacy_windows=False, force_terminal=True)



def setup_logger() -> None:
    """Configures loguru logger with console and file rotation."""
    logger.remove()
    
    # Console logging
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
        colorize=True,
    )

    # File logging
    log_file = config.logs_dir / "agent.log"
    config.logs_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(log_file),
        rotation="10 MB",
        retention="14 days",
        level="DEBUG",
        encoding="utf-8",
    )


def display_post_summary(post: dict, title: str = "Extracted Post") -> None:
    """Renders a formatted table of the extracted LinkedIn post."""
    table = Table(title=title, show_header=True, header_style="bold magenta")
    table.add_column("Field", style="cyan", width=15)
    table.add_column("Value", style="white")

    table.add_row("URL", post.get("url") or "[dim]N/A[/dim]")
    table.add_row("Date", post.get("date") or "[dim]N/A[/dim]")
    table.add_row("Hashtags", ", ".join([f"#{t}" for t in post.get("hashtags", [])]) or "[dim]None[/dim]")
    
    content = post.get("content", "")
    preview = (content[:250] + "...\n[dim](truncated for preview)[/dim]") if len(content) > 250 else content
    table.add_row("Content", preview)

    console.print(table)


def run_sync_pipeline(force: bool = False, dry_run: bool = False, headless: Optional[bool] = None) -> bool:
    """
    Executes the complete scrape -> deduplicate -> webhook dispatch workflow.
    """
    console.print(Panel.fit("[bold blue]🚀 Starting LinkedIn Sync AI Agent Pipeline[/bold blue]", border_style="blue"))
    
    state_mgr = StateManager()
    scraper = LinkedInScraper(headless=headless)
    
    logger.info("Step 1: Scraping latest post from LinkedIn...")
    post = scraper.scrape_latest_post()

    if not post:
        logger.error("❌ Failed to scrape latest post from LinkedIn.")
        return False

    display_post_summary(post)

    # Step 2: Check Deduplication
    if not force and state_mgr.is_already_synced(post["url"], post["content"]):
        logger.info("ℹ️ Post has already been synced previously. No webhook dispatch required.")
        console.print("[yellow]⚠️ Bu gönderi zaten daha önce senkronize edilmiş. Webhook atlanıyor.[/yellow]")
        return True

    # Step 3: Handle Dry Run
    if dry_run:
        console.print("[bold yellow]🧪 DRY-RUN MODU: Webhook fırlatılmadı (test amaçlı durduruldu).[/bold yellow]")
        return True

    # Step 4: Dispatch Webhook
    logger.info("Step 2: Dispatching post to webhook endpoint...")
    dispatcher = WebhookDispatcher()
    success, status_code, response_text = dispatcher.send(post)

    if success:
        state_mgr.record_sync(post)
        console.print(f"[bold green]✅ Webhook başarıyla gönderildi ve durum kaydedildi! (Status: {status_code})[/bold green]")
        return True
    else:
        console.print(f"[bold red]❌ Webhook gönderimi başarısız oldu! (Status: {status_code}) - {response_text}[/bold red]")
        return False


def test_webhook_connection() -> None:
    """Sends a mock test payload to the webhook endpoint."""
    console.print(Panel.fit("[bold cyan]🧪 Testing Webhook Connection[/bold cyan]"))
    dispatcher = WebhookDispatcher()
    test_payload = {
        "content": "Test payload from LinkedIn Sync AI Agent by Doğukan Ergin. #Test #AI",
        "url": "https://www.linkedin.com/feed/update/urn:li:activity:0000000000000000000/",
        "date": "Just now",
        "hashtags": ["Test", "AI"],
        "is_test": True,
    }
    success, status_code, response_text = dispatcher.send(test_payload)
    if success:
        console.print(f"[bold green]✅ Webhook bağlantı testi başarılı! (HTTP {status_code})[/bold green]")
    else:
        console.print(f"[bold red]❌ Webhook bağlantı testi başarısız! (HTTP {status_code}) - {response_text}[/bold red]")


def start_scheduler(force: bool = False, headless: Optional[bool] = None) -> None:
    """Runs continuous scheduler loop executing sync daily."""
    import schedule

    target_time = config.sync_schedule_time
    console.print(Panel.fit(
        f"[bold green]⏰ Scheduler Mode Started[/bold green]\n"
        f"Ajan her gün [bold yellow]{target_time}[/bold yellow] saatinde otomatik olarak çalışacak.\n"
        f"[dim]Durdurmak için Ctrl+C tuşlarına basabilirsiniz.[/dim]",
        border_style="green"
    ))

    def job():
        logger.info(f"Scheduled job triggered at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        run_sync_pipeline(force=force, headless=headless)

    # Run once at startup
    job()

    schedule.every().day.at(target_time).do(job)

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        console.print("\n[yellow]Scheduler durduruldu. Çıkış yapılıyor...[/yellow]")


def main():
    setup_logger()

    parser = argparse.ArgumentParser(description="Autonomous LinkedIn Sync AI Agent for dogukanergin.com")
    parser.add_argument("--run-once", action="store_true", help="Run the sync pipeline once and exit (Default).")
    parser.add_argument("--schedule", action="store_true", help="Run in daily scheduler mode.")
    parser.add_argument("--login", action="store_true", help="Launch interactive browser to log in and save cookies.")
    parser.add_argument("--dry-run", action="store_true", help="Scrape post and output payload without sending webhook.")
    parser.add_argument("--force", action="store_true", help="Force webhook dispatch even if post was already synced.")
    parser.add_argument("--test-webhook", action="store_true", help="Send a mock test payload to the webhook endpoint.")
    parser.add_argument("--headless", type=str, choices=["true", "false"], default=None, help="Override headless mode.")

    args = parser.parse_args()

    headless_override = None
    if args.headless is not None:
        headless_override = (args.headless.lower() == "true")

    if args.login:
        scraper = LinkedInScraper(headless=False)
        scraper.interactive_login()
        return

    if args.test_webhook:
        test_webhook_connection()
        return

    if args.schedule:
        start_scheduler(force=args.force, headless=headless_override)
        return

    # Default action: run once
    run_sync_pipeline(force=args.force, dry_run=args.dry_run, headless=headless_override)


if __name__ == "__main__":
    main()
