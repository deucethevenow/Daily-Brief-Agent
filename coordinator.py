"""Main Coordinator Agent - Orchestrates the daily brief workflow."""
from datetime import datetime
from typing import Dict, Any
from config import Config
from utils import setup_logger, filter_new_mentions, mark_mentions_as_processed
from integrations import AirtableClient, AsanaClient, SlackClient
from agents import MeetingAnalyzerAgent, AsanaSummaryAgent, MentionResponseAgent

logger = setup_logger(__name__)


class DailyBriefCoordinator:
    """Main coordinator that orchestrates all subagents and integrations."""

    def __init__(self):
        """Initialize the coordinator and all subagents."""
        logger.info("Initializing Daily Brief Coordinator")

        # Initialize integrations
        self.airtable = AirtableClient()
        self.asana = AsanaClient()
        self.slack = SlackClient()

        # Initialize agents
        self.meeting_analyzer = MeetingAnalyzerAgent()
        self.asana_summary_agent = AsanaSummaryAgent()
        self.mention_response_agent = MentionResponseAgent()

        logger.info("Daily Brief Coordinator initialized successfully")

    def run_daily_brief(self, override_date: datetime = None) -> bool:
        """Execute the daily brief workflow.

        Args:
            override_date: Optional datetime to use instead of now() (for testing)

        Returns:
            True if successful, False otherwise
        """
        try:
            if override_date:
                today = override_date.date()
            else:
                today = datetime.now(Config.TIMEZONE).date()
            is_friday = today.weekday() == 4  # Friday is day 4

            logger.info(f"Running daily brief for {today} (Friday: {is_friday})")

            # Step 1: Fetch today's meetings from Airtable
            logger.info("Step 1: Fetching today's meetings from Airtable")
            try:
                meetings = self.airtable.get_today_meetings()
            except Exception as e:
                error_msg = f"Failed to fetch meetings from Airtable: {str(e)}"
                logger.error(error_msg, exc_info=True)
                self._send_error_notification(error_msg + "\n\nDaily brief cannot continue without meeting data.")
                return False

            if not meetings:
                logger.warning("No meetings found for today")

            # Step 2: Analyze meetings and extract action items
            logger.info("Step 2: Analyzing meetings and extracting action items")
            try:
                analysis_result = self.meeting_analyzer.batch_analyze_with_context(meetings)
                action_items = analysis_result.get('action_items', [])
            except Exception as e:
                error_msg = f"Critical failure in meeting analysis: {str(e)}"
                logger.error(error_msg, exc_info=True)
                self._send_error_notification(error_msg + "\n\nNo action items extracted from today's meetings.")
                action_items = []
                analysis_result = {'action_items': [], 'summary': 'Analysis failed'}

            logger.info(f"Found {len(action_items)} action items from meetings")

            # Show ALL action items from meetings where you were involved
            # No filtering by assignee - you'll see all action items from your meetings
            logger.info(f"Showing all {len(action_items)} action items from meetings where you were host/participant")
            action_items_to_show = action_items

            # Step 3: Optionally create Asana tasks (based on config)
            # Note: Only creates tasks for the filtered items (your action items)
            if Config.AUTO_CREATE_TASKS:
                logger.info("Step 3: Creating Asana tasks for your action items (AUTO_CREATE_TASKS=true)")
                created_count = 0
                for item in action_items_to_show:
                    try:
                        task = self.asana.create_task(
                            title=item['title'],
                            notes=f"{item['description']}\n\nFrom: {item.get('meeting_title', 'Meeting')}\nDate: {item.get('meeting_date', '')}",
                            due_date=item.get('due_date')
                        )
                        created_count += 1
                        logger.info(f"Created task: {item['title']}")
                    except Exception as e:
                        logger.error(f"Failed to create task '{item['title']}': {e}")
                logger.info(f"Created {created_count}/{len(action_items_to_show)} tasks in Asana")
            else:
                logger.info("Step 3: Suggesting action items for manual review (AUTO_CREATE_TASKS=false)")
                logger.info("To enable auto-creation, set AUTO_CREATE_TASKS=true in .env")

            # Step 4: Fetch Asana data
            logger.info("Step 4: Fetching Asana task data")
            try:
                completed_tasks = self.asana.get_completed_tasks_today()
                overdue_tasks = self.asana.get_overdue_tasks()
            except Exception as e:
                error_msg = f"Failed to fetch Asana tasks: {str(e)}"
                logger.error(error_msg, exc_info=True)
                self._send_error_notification(error_msg + "\n\nDaily brief will be sent without Asana task data.")
                completed_tasks = []
                overdue_tasks = []

            logger.info(f"Completed tasks today: {len(completed_tasks)}")
            logger.info(f"Overdue tasks: {len(overdue_tasks)}")

            # Step 4.5: Check for unanswered @mentions
            logger.info("Step 4.5: Checking for unanswered @mentions")
            unanswered_mentions = []
            new_mentions_for_task = []
            try:
                if Config.MONITORED_USER_NAMES:
                    # Get all unanswered mentions
                    all_unanswered = self.asana.get_unanswered_mentions(
                        Config.MONITORED_USER_NAMES,
                        Config.MENTION_LOOKBACK_HOURS
                    )

                    if all_unanswered:
                        # Filter out already-processed mentions (to avoid duplicate tasks)
                        new_mentions_for_task = filter_new_mentions(all_unanswered)
                        logger.info(f"Found {len(all_unanswered)} unanswered mentions ({len(new_mentions_for_task)} new)")

                        # Draft responses for ALL mentions (for Slack display)
                        unanswered_mentions = self.mention_response_agent.batch_draft_responses(
                            all_unanswered
                        )

                        # Create Asana task ONLY for NEW mentions (not previously processed)
                        if new_mentions_for_task:
                            # Get the new mentions with their drafted responses
                            new_mention_ids = {m.get('mention_story_gid') for m in new_mentions_for_task}
                            new_mentions_with_drafts = [
                                m for m in unanswered_mentions
                                if m.get('mention_story_gid') in new_mention_ids
                            ]

                            logger.info(f"Creating Asana task for {len(new_mentions_with_drafts)} new mentions")
                            try:
                                task_result = self.asana.create_respond_to_mentions_task(new_mentions_with_drafts)
                                if task_result:
                                    logger.info(f"Created respond-to-mentions task: {task_result.get('gid')}")
                                    # Mark these mentions as processed so they won't be added again
                                    mark_mentions_as_processed(new_mentions_with_drafts)
                            except Exception as e:
                                logger.error(f"Failed to create respond-to-mentions task: {e}")
                        else:
                            logger.info("All mentions already processed - no new Asana task needed")
                    else:
                        logger.info("No unanswered mentions found")
                else:
                    logger.info("No monitored users configured, skipping mention check")
            except Exception as e:
                logger.error(f"Failed to fetch unanswered mentions: {e}")
                unanswered_mentions = []

            # Step 5: Generate report based on day
            if is_friday:
                logger.info("Step 5: Generating weekly summary (Friday)")
                report_data = self._generate_weekly_report(
                    action_items=action_items_to_show,
                    completed_tasks=completed_tasks,
                    overdue_tasks=overdue_tasks,
                    unanswered_mentions=unanswered_mentions,
                    date_override=override_date
                )
                self.slack.send_weekly_summary(report_data)
            else:
                logger.info("Step 5: Generating daily report")
                report_data = self._generate_daily_report(
                    action_items=action_items_to_show,
                    completed_tasks=completed_tasks,
                    overdue_tasks=overdue_tasks,
                    unanswered_mentions=unanswered_mentions,
                    date_override=override_date
                )
                self.slack.send_daily_brief(report_data)

            logger.info("Daily brief completed successfully")
            return True

        except Exception as e:
            logger.error(f"Error running daily brief: {e}", exc_info=True)
            self._send_error_notification(str(e))
            return False

    def _generate_daily_report(self, action_items: list, completed_tasks: list,
                              overdue_tasks: list, unanswered_mentions: list = None,
                              date_override: datetime = None) -> Dict[str, Any]:
        """Generate the daily report data.

        Args:
            action_items: List of action items extracted from meetings
            completed_tasks: List of tasks completed today
            overdue_tasks: List of overdue tasks
            unanswered_mentions: List of unanswered @mentions with draft responses
            date_override: Optional date override for testing

        Returns:
            Dictionary with formatted report data
        """
        today = date_override if date_override else datetime.now(Config.TIMEZONE)

        # Get AI-generated summary
        summary = self.asana_summary_agent.generate_daily_summary(
            completed_tasks, overdue_tasks
        )

        return {
            'date': today.strftime('%B %d, %Y'),
            'timestamp': today.strftime('%I:%M %p %Z'),
            'action_items': action_items,
            'completed_tasks': completed_tasks,
            'overdue_tasks': overdue_tasks,
            'unanswered_mentions': unanswered_mentions or [],
            'summary': summary.get('overview', ''),
            'highlights': summary.get('team_highlights', []),
            'concerns': summary.get('concerns', []),
            'recommendation': summary.get('recommendation', '')
        }

    def _generate_weekly_report(self, action_items: list, completed_tasks: list,
                               overdue_tasks: list, unanswered_mentions: list = None,
                               date_override: datetime = None) -> Dict[str, Any]:
        """Generate the weekly summary report data.

        Args:
            action_items: List of action items from today's meetings
            completed_tasks: List of tasks completed today
            overdue_tasks: List of overdue tasks
            unanswered_mentions: List of unanswered @mentions with draft responses
            date_override: Optional date override for testing

        Returns:
            Dictionary with formatted weekly report data
        """
        today = date_override if date_override else datetime.now(Config.TIMEZONE)

        # Fetch weekly data
        week_meetings = self.airtable.get_week_meetings()
        week_completed = self.asana.get_completed_tasks_this_week()

        # Get AI-generated weekly summary
        summary = self.asana_summary_agent.generate_weekly_summary(
            week_completed, overdue_tasks
        )

        return {
            'date': f"Week of {today.strftime('%B %d, %Y')}",
            'timestamp': today.strftime('%I:%M %p %Z'),
            'overview': summary.get('overview', ''),
            'major_accomplishments': summary.get('major_accomplishments', []),
            'team_summary': summary.get('team_summary', ''),
            'next_week_focus': summary.get('next_week_focus', []),
            'action_items': action_items,
            'completed_tasks': completed_tasks,
            'overdue_tasks': overdue_tasks,
            'unanswered_mentions': unanswered_mentions or [],
            'week_total_completed': len(week_completed),
            'meetings_this_week': len(week_meetings)
        }

    def _send_error_notification(self, error_message: str):
        """Send an error notification to Slack if the daily brief fails.

        Args:
            error_message: The error message to send
        """
        try:
            self.slack.send_message(
                text=f"⚠️ Daily Brief Failed",
                blocks=[
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "⚠️ Daily Brief Error"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"The daily brief failed to complete:\n\n```{error_message}```"
                        }
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"Check the logs for more details."
                            }
                        ]
                    }
                ]
            )
        except Exception as e:
            logger.error(f"Failed to send error notification: {e}")

    def test_connections(self) -> Dict[str, bool]:
        """Test all API connections.

        Returns:
            Dictionary with connection test results
        """
        results = {}

        # Test Airtable
        try:
            self.airtable.get_today_meetings()
            results['airtable'] = True
            logger.info("✓ Airtable connection successful")
        except Exception as e:
            results['airtable'] = False
            logger.error(f"✗ Airtable connection failed: {e}")

        # Test Asana
        try:
            self.asana.get_overdue_tasks()
            results['asana'] = True
            logger.info("✓ Asana connection successful")
        except Exception as e:
            results['asana'] = False
            logger.error(f"✗ Asana connection failed: {e}")

        # Test Slack
        try:
            self.slack.client.auth_test()
            results['slack'] = True
            logger.info("✓ Slack connection successful")
        except Exception as e:
            results['slack'] = False
            logger.error(f"✗ Slack connection failed: {e}")

        # Test Claude API
        try:
            test_response = self.meeting_analyzer.client.messages.create(
                model=self.meeting_analyzer.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "test"}]
            )
            results['claude'] = True
            logger.info("✓ Claude API connection successful")
        except Exception as e:
            results['claude'] = False
            logger.error(f"✗ Claude API connection failed: {e}")

        return results


def main():
    """Main entry point for running the daily brief manually."""
    try:
        # Validate configuration
        Config.validate()

        # Create coordinator
        coordinator = DailyBriefCoordinator()

        # Test connections
        logger.info("Testing API connections...")
        test_results = coordinator.test_connections()

        all_passed = all(test_results.values())
        if not all_passed:
            logger.error("Some API connections failed. Please check your configuration.")
            return False

        # Run daily brief
        logger.info("Starting daily brief...")
        success = coordinator.run_daily_brief()

        if success:
            logger.info("✓ Daily brief completed successfully!")
        else:
            logger.error("✗ Daily brief failed. Check logs for details.")

        return success

    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    main()
