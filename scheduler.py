"""Scheduler for running the daily brief at 4pm MT every day."""
import schedule
import time
from datetime import datetime
from config import Config
from coordinator import DailyBriefCoordinator
from utils import setup_logger

logger = setup_logger(__name__)


def run_scheduled_brief():
    """Execute the daily brief via the coordinator."""
    logger.info("=" * 80)
    logger.info(f"Scheduled run triggered at {datetime.now(Config.TIMEZONE)}")
    logger.info("=" * 80)

    coordinator = None
    try:
        coordinator = DailyBriefCoordinator()
        success = coordinator.run_daily_brief()

        if success:
            logger.info("✓ Scheduled daily brief completed successfully")
        else:
            logger.error("✗ Scheduled daily brief failed")
            if coordinator:
                coordinator._send_error_notification("Daily brief completed but returned failure status. Check logs for details.")

    except Exception as e:
        logger.error(f"Fatal error in scheduled brief: {e}", exc_info=True)
        # Try to send error notification to Slack
        try:
            if not coordinator:
                coordinator = DailyBriefCoordinator()
            coordinator._send_error_notification(f"Scheduler crashed: {str(e)}")
        except:
            logger.error("Failed to send error notification to Slack")


def start_scheduler():
    """Start the scheduler to run daily brief at 4pm MT."""
    try:
        # Validate configuration
        Config.validate()
        logger.info("Configuration validated successfully")

        # Schedule the daily brief at 4:00 PM MT
        schedule.every().day.at(Config.DAILY_RUN_TIME).do(run_scheduled_brief)

        logger.info(f"Scheduler started. Daily brief will run at {Config.DAILY_RUN_TIME} {Config.TIMEZONE}")
        logger.info(f"Current time: {datetime.now(Config.TIMEZONE).strftime('%I:%M %p %Z')}")
        logger.info("Press Ctrl+C to stop the scheduler")
        logger.info("=" * 80)

        # Run immediately on startup for testing (comment out in production)
        # logger.info("Running initial test brief...")
        # run_scheduled_brief()

        # Keep the scheduler running
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute

    except KeyboardInterrupt:
        logger.info("\nScheduler stopped by user")
    except Exception as e:
        logger.error(f"Fatal error in scheduler: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    start_scheduler()
