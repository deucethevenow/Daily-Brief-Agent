"""Slack client for sending daily brief messages."""
from typing import List, Dict, Any
import ssl
import certifi
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from config import Config
from utils import setup_logger

logger = setup_logger(__name__)

# Fix SSL certificate verification for macOS
ssl_context = ssl.create_default_context(cafile=certifi.where())


class SlackClient:
    """Client for sending messages to Slack."""

    def __init__(self):
        """Initialize the Slack client."""
        self.client = WebClient(token=Config.SLACK_BOT_TOKEN, ssl=ssl_context)
        self.channel_id = Config.SLACK_CHANNEL_ID
        logger.info("SlackClient initialized")

    def send_message(self, text: str, blocks: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a message to the configured Slack channel.

        Args:
            text: Plain text message (fallback and notification text)
            blocks: Optional Slack Block Kit blocks for rich formatting

        Returns:
            Slack API response
        """
        try:
            response = self.client.chat_postMessage(
                channel=self.channel_id,
                text=text,
                blocks=blocks,
                unfurl_links=False,
                unfurl_media=False
            )

            logger.info(f"Message sent to Slack channel {self.channel_id}")
            return response

        except SlackApiError as e:
            logger.error(f"Error sending Slack message: {e.response['error']}")
            raise

    def send_daily_brief(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send a formatted daily brief message.

        Args:
            report_data: Dictionary containing report sections

        Returns:
            Slack API response
        """
        # Send unanswered mentions as separate detailed messages FIRST
        if report_data.get('unanswered_mentions'):
            self._send_mentions_detailed(report_data['unanswered_mentions'])

        # Send completed tasks as separate detailed messages
        if report_data.get('completed_tasks'):
            self._send_completed_tasks_detailed(report_data['completed_tasks'])

        # Send overdue tasks as separate detailed messages
        if report_data.get('overdue_tasks'):
            self._send_overdue_tasks_detailed(report_data['overdue_tasks'])

        # Then send the main brief summary (compact version)
        blocks = self._build_daily_brief_blocks(report_data)
        text = f"📊 Daily Brief for {report_data.get('date', 'Today')}"

        return self.send_message(text, blocks)

    def _send_mentions_detailed(self, mentions: List[Dict[str, Any]]) -> None:
        """Send unanswered mentions as separate detailed messages, grouped by person.

        Each mention gets its own message with full context and draft response.
        Shows ALL monitored users from config, even those with 0 mentions.

        Args:
            mentions: List of unanswered mention dictionaries
        """
        from config import Config

        # Get all monitored users from config
        all_monitored_users = Config.MONITORED_USER_NAMES or []

        # Group mentions by mentioned user
        by_user = {user: [] for user in all_monitored_users}  # Initialize all users
        for mention in mentions:
            user = mention.get('mentioned_user_name', 'Unknown')
            if user not in by_user:
                by_user[user] = []
            by_user[user].append(mention)

        total_mentions = len(mentions)

        # Send header message
        if total_mentions > 0:
            header_text = f"📬 {total_mentions} Unanswered @Mention{'s' if total_mentions != 1 else ''} Need Your Response"
        else:
            header_text = "📬 No Unanswered @Mentions - You're All Caught Up!"

        header_blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": header_text,
                    "emoji": True
                }
            },
            {
                "type": "context",
                "elements": [{
                    "type": "mrkdwn",
                    "text": "_Click 'Open in Asana' to respond. Draft responses are provided below each message._" if total_mentions > 0 else f"_Monitoring: {', '.join(all_monitored_users)}_"
                }]
            }
        ]
        self.send_message("📬 Unanswered @Mentions", header_blocks)

        # Send mentions grouped by user - show ALL monitored users
        for user_name in all_monitored_users:
            user_mentions = by_user.get(user_name, [])
            count = len(user_mentions)

            # Send section header for this user
            if count > 0:
                section_text = f"*━━━━━ For {user_name} ({count} message{'s' if count != 1 else ''}) ━━━━━*"
            else:
                section_text = f"*━━━━━ For {user_name} ━━━━━*\n✅ _No unanswered mentions - all caught up!_"

            section_blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": section_text
                    }
                }
            ]
            self.send_message(f"Mentions for {user_name}", section_blocks)

            # Send each mention for this user
            for mention in user_mentions:
                self._send_single_mention(mention)

    def _send_single_mention(self, mention: Dict[str, Any]) -> None:
        """Send a single mention as a detailed message.

        Args:
            mention: Dictionary with mention details
        """
        hours_ago = mention.get('hours_since_mention', 0)
        if hours_ago < 1:
            time_str = "just now"
        elif hours_ago < 24:
            time_str = f"{int(hours_ago)} hours ago"
        else:
            time_str = f"{int(hours_ago / 24)} days ago"

        confidence = mention.get('response_confidence', 'low')
        confidence_emoji = {'high': '✅', 'medium': '🟡', 'low': '🔴'}.get(confidence, '⚪')
        confidence_text = {'high': 'High confidence', 'medium': 'Medium confidence', 'low': 'Low confidence'}.get(confidence, '')

        # Truncate comment text to fit Slack's block limit (leave room for formatting)
        comment_text = mention.get('comment_text', 'No comment text')
        if len(comment_text) > 800:
            comment_text = comment_text[:800] + "..."

        task_name = mention.get('task_name', 'Unknown Task')[:80]
        project_name = mention.get('project_name', 'No Project')[:50]

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*<{mention.get('task_url', '#')}|{task_name}>*\n_{project_name}_"
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Open in Asana",
                        "emoji": True
                    },
                    "url": mention.get('task_url', 'https://app.asana.com'),
                    "action_id": f"open_task_{mention.get('task_gid', 'unknown')}",
                    "style": "primary"
                }
            },
            {
                "type": "context",
                "elements": [{
                    "type": "mrkdwn",
                    "text": f"*{mention.get('author_name', 'Someone')}* mentioned *{mention.get('mentioned_user_name', 'you')}* • {time_str}"
                }]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f">{comment_text}"
                }
            },
            {"type": "divider"}
        ]

        # Send the mention context message first
        self.send_message(
            f"@mention from {mention.get('author_name', 'Someone')} on {task_name}",
            blocks
        )

        # Send suggested response as separate message(s) if available
        if mention.get('suggested_response'):
            response_text = mention['suggested_response']

            # Split into chunks if longer than 2800 chars (Slack limit is 3000, leave room for formatting)
            chunk_size = 2800
            chunks = []
            while response_text:
                if len(response_text) <= chunk_size:
                    chunks.append(response_text)
                    break
                # Find a good break point (newline or space)
                break_point = response_text.rfind('\n', 0, chunk_size)
                if break_point == -1 or break_point < chunk_size // 2:
                    break_point = response_text.rfind(' ', 0, chunk_size)
                if break_point == -1 or break_point < chunk_size // 2:
                    break_point = chunk_size
                chunks.append(response_text[:break_point])
                response_text = response_text[break_point:].lstrip()

            # Send first chunk with header
            first_chunk = chunks[0]
            response_blocks = [{
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{confidence_emoji} *Suggested Response* ({confidence_text}):\n\n{first_chunk}"
                }
            }]
            self.send_message(f"Draft response for: {task_name}", response_blocks)

            # Send remaining chunks as continuation messages
            for i, chunk in enumerate(chunks[1:], 2):
                continuation_blocks = [{
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"_{f'(continued {i}/{len(chunks)})':}_\n\n{chunk}"
                    }
                }]
                self.send_message(f"Draft response (continued) for: {task_name}", continuation_blocks)

        return  # Already sent messages above

    def _send_completed_tasks_detailed(self, completed_tasks: List[Dict[str, Any]]) -> None:
        """Send all completed tasks as separate detailed messages, grouped by person.

        Args:
            completed_tasks: List of completed task dictionaries
        """
        if not completed_tasks:
            return

        # Group by assignee
        by_person = {}
        for task in completed_tasks:
            assignee = task.get('assignee', 'Unassigned')
            if assignee not in by_person:
                by_person[assignee] = []
            by_person[assignee].append(task)

        # Sort by task count (most productive first)
        sorted_people = sorted(by_person.items(), key=lambda x: len(x[1]), reverse=True)

        # Send header
        header_blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🎯 Tasks Completed Today ({len(completed_tasks)} total)",
                    "emoji": True
                }
            }
        ]
        self.send_message("Completed tasks details", header_blocks)

        # Send each person's tasks as a separate message
        for person, tasks in sorted_people:
            # Build task list - show ALL tasks
            task_lines = []
            for task in tasks:
                task_name = task.get('name', 'Unknown Task')
                task_gid = task.get('gid', '')
                project = task.get('project', '')

                # Create clickable link
                if task_gid:
                    line = f"• <https://app.asana.com/0/0/{task_gid}|{task_name}>"
                else:
                    line = f"• {task_name}"

                if project:
                    line += f" _({project})_"

                task_lines.append(line)

            # Split into chunks if needed (Slack 3000 char limit)
            # Each task line is roughly 80-150 chars, so ~20 tasks per message
            chunk_size = 20
            chunks = [task_lines[i:i+chunk_size] for i in range(0, len(task_lines), chunk_size)]

            for i, chunk in enumerate(chunks):
                if len(chunks) == 1:
                    header_text = f"*{person}* ({len(tasks)} task{'s' if len(tasks) != 1 else ''})"
                else:
                    header_text = f"*{person}* ({len(tasks)} tasks) - Part {i+1}/{len(chunks)}"

                blocks = [{
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": header_text + "\n" + "\n".join(chunk)
                    }
                }]
                self.send_message(f"Completed tasks for {person}", blocks)

    def _send_overdue_tasks_detailed(self, overdue_tasks: List[Dict[str, Any]]) -> None:
        """Send all overdue tasks as separate detailed messages, grouped by person.

        Args:
            overdue_tasks: List of overdue task dictionaries
        """
        if not overdue_tasks:
            return

        from config import Config

        # Group by assignee
        by_person = {}
        for task in overdue_tasks:
            assignee = task.get('assignee', 'Unassigned')
            if assignee not in by_person:
                by_person[assignee] = []
            by_person[assignee].append(task)

        # Sort by task count (most overdue first)
        sorted_people = sorted(by_person.items(), key=lambda x: len(x[1]), reverse=True)

        # Build age limit note
        age_limit_note = ""
        if Config.ASANA_TASK_AGE_LIMIT_DAYS > 0:
            age_limit_note = f" (last {Config.ASANA_TASK_AGE_LIMIT_DAYS} days)"

        # Send header
        header_blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"⚠️ Overdue Tasks ({len(overdue_tasks)} total{age_limit_note})",
                    "emoji": True
                }
            }
        ]
        self.send_message("Overdue tasks details", header_blocks)

        # Send each person's tasks as a separate message
        for person, tasks in sorted_people:
            # Sort by days overdue (most overdue first)
            tasks_sorted = sorted(tasks, key=lambda x: x.get('days_overdue', 0), reverse=True)

            # Build task list - show ALL tasks with days overdue
            task_lines = []
            for task in tasks_sorted:
                task_name = task.get('name', 'Unknown Task')
                task_gid = task.get('gid', '')
                days_overdue = task.get('days_overdue', 0)
                project = task.get('project', '')

                # Urgency emoji based on days overdue
                if days_overdue >= 14:
                    urgency = "🔴"
                elif days_overdue >= 7:
                    urgency = "🟠"
                else:
                    urgency = "🟡"

                # Create clickable link
                if task_gid:
                    line = f"{urgency} <https://app.asana.com/0/0/{task_gid}|{task_name}> ({days_overdue}d overdue)"
                else:
                    line = f"{urgency} {task_name} ({days_overdue}d overdue)"

                if project:
                    line += f" _({project})_"

                task_lines.append(line)

            # Split into chunks if needed (Slack 3000 char limit)
            chunk_size = 15  # Fewer per chunk since overdue lines are longer
            chunks = [task_lines[i:i+chunk_size] for i in range(0, len(task_lines), chunk_size)]

            for i, chunk in enumerate(chunks):
                if len(chunks) == 1:
                    header_text = f"*{person}* ({len(tasks)} overdue task{'s' if len(tasks) != 1 else ''})"
                else:
                    header_text = f"*{person}* ({len(tasks)} overdue) - Part {i+1}/{len(chunks)}"

                blocks = [{
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": header_text + "\n" + "\n".join(chunk)
                    }
                }]
                self.send_message(f"Overdue tasks for {person}", blocks)

    def send_weekly_summary(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send a formatted weekly summary message.

        Args:
            report_data: Dictionary containing weekly report sections

        Returns:
            Slack API response
        """
        # Send unanswered mentions as separate detailed messages FIRST
        if report_data.get('unanswered_mentions'):
            self._send_mentions_detailed(report_data['unanswered_mentions'])

        blocks = self._build_weekly_summary_blocks(report_data)
        text = f"📈 Weekly Summary for {report_data.get('date', 'This Week')}"

        return self.send_message(text, blocks)

    def _build_daily_brief_blocks(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build Slack blocks for daily brief.

        Args:
            data: Report data with sections

        Returns:
            List of Slack Block Kit blocks (max 48 to stay under Slack's 50 limit)
        """
        MAX_BLOCKS = 48  # Slack limit is 50, leave room for safety

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📊 Daily Brief - {data.get('date', 'Today')}",
                    "emoji": True
                }
            },
            {"type": "divider"}
        ]

        # Note: Unanswered @Mentions are sent as separate messages before this
        # to allow full draft responses to be visible

        # Action Items from Meetings - use compact format
        if data.get('action_items'):
            from config import Config

            if Config.AUTO_CREATE_TASKS:
                header_text = f"*✅ Action Items Created in Asana* ({len(data['action_items'])} from today's calls)"
            else:
                header_text = f"*💡 Action Items from Today's Meetings* ({len(data['action_items'])} items)"

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": header_text
                }
            })

            # Compact format: group action items into fewer blocks (5 items per block max)
            items_to_show = data['action_items'][:8]  # Show max 8 items
            item_lines = []
            for item in items_to_show:
                priority_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(item.get('priority', ''), '')
                assignee = item.get('assignee', 'Unassigned')
                line = f"• {priority_emoji} *{item['title'][:60]}{'...' if len(item.get('title', '')) > 60 else ''}* ({assignee})"
                item_lines.append(line)

            # Split into chunks of 4 items per block to stay under 3000 char limit
            for i in range(0, len(item_lines), 4):
                chunk = item_lines[i:i+4]
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": '\n'.join(chunk)
                    }
                })

            if len(data['action_items']) > 8:
                blocks.append({
                    "type": "context",
                    "elements": [{
                        "type": "mrkdwn",
                        "text": f"_...and {len(data['action_items']) - 8} more action items from meetings_"
                    }]
                })

            blocks.append({"type": "divider"})

        # Completed Tasks - just show header in main brief, details sent separately
        if data.get('completed_tasks'):
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🎯 Tasks Completed Today* ({len(data['completed_tasks'])} total)\n_See detailed list below_"
                }
            })
            blocks.append({"type": "divider"})

        # Overdue Tasks - just show header in main brief, details sent separately
        if data.get('overdue_tasks'):
            from config import Config
            age_limit_note = ""
            if Config.ASANA_TASK_AGE_LIMIT_DAYS > 0:
                age_limit_note = f" (last {Config.ASANA_TASK_AGE_LIMIT_DAYS} days)"

            # Count by person for quick summary
            overdue_by_person = {}
            for task in data['overdue_tasks']:
                assignee = task.get('assignee', 'Unassigned')
                if assignee not in overdue_by_person:
                    overdue_by_person[assignee] = 0
                overdue_by_person[assignee] += 1

            # Sort by count
            sorted_overdue = sorted(overdue_by_person.items(), key=lambda x: x[1], reverse=True)
            person_summaries = [f"*{person}*: {count}" for person, count in sorted_overdue]
            summary_text = ' • '.join(person_summaries)

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*⚠️ Overdue Tasks* ({len(data['overdue_tasks'])} total{age_limit_note})\n{summary_text}\n_See detailed list above_"
                }
            })
            blocks.append({"type": "divider"})

        # AI Insights (if available)
        if data.get('summary') or data.get('highlights') or data.get('concerns'):
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*🤖 AI Insights*"
                }
            })

            # Overview summary
            if data.get('summary'):
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"_{data['summary']}_"
                    }
                })

            # Team highlights
            if data.get('highlights'):
                highlights_text = "*Team Highlights:*\n" + '\n'.join([f"• {h}" for h in data['highlights']])
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": highlights_text
                    }
                })

            # Concerns
            if data.get('concerns'):
                concerns_text = "*Concerns:*\n" + '\n'.join([f"⚠️ {c}" for c in data['concerns']])
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": concerns_text
                    }
                })

            # Recommendation
            if data.get('recommendation'):
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*💡 Recommendation:* {data['recommendation']}"
                    }
                })

        # Footer
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"_Generated at {data.get('timestamp', 'now')}_"
                }
            ]
        })

        return blocks

    def _build_unanswered_mentions_blocks(self, mentions: List[Dict[str, Any]], total_count: int = None) -> List[Dict[str, Any]]:
        """Build Slack blocks for unanswered @mentions section.

        Args:
            mentions: List of unanswered mention dictionaries (may be truncated)
            total_count: Total number of mentions (for showing "and X more")

        Returns:
            List of Slack Block Kit blocks for mentions section
        """
        if not mentions:
            return []

        if total_count is None:
            total_count = len(mentions)

        blocks = [
            {"type": "divider"},
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📬 Unanswered @Mentions",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{total_count} message{'s' if total_count != 1 else ''} need{'s' if total_count == 1 else ''} your response:*"
                }
            }
        ]

        for mention in mentions:
            hours_ago = mention.get('hours_since_mention', 0)
            if hours_ago < 1:
                time_str = "just now"
            elif hours_ago < 24:
                time_str = f"{int(hours_ago)}h ago"
            else:
                time_str = f"{int(hours_ago / 24)}d ago"

            # Truncate comment if too long
            comment_text = mention.get('comment_text', '')
            if len(comment_text) > 150:
                comment_text = comment_text[:150] + "..."

            # Build compact mention block
            mention_text = (
                f"<{mention.get('task_url', '#')}|*{mention.get('task_name', 'Unknown Task')[:50]}*>\n"
                f"*{mention.get('author_name', 'Someone')}* → *{mention.get('mentioned_user_name', 'Unknown')}* ({time_str}):\n"
                f">{comment_text}"
            )

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": mention_text
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Open in Asana",
                        "emoji": True
                    },
                    "url": mention.get('task_url', 'https://app.asana.com'),
                    "action_id": f"open_task_{mention.get('task_gid', 'unknown')}"
                }
            })

            # Add suggested response if available (compact)
            if mention.get('suggested_response'):
                confidence = mention.get('response_confidence', 'low')
                confidence_emoji = {'high': '✅', 'medium': '🟡', 'low': '🔴'}.get(confidence, '⚪')

                # Truncate response if too long
                response_text = mention['suggested_response']
                if len(response_text) > 200:
                    response_text = response_text[:200] + "..."

                blocks.append({
                    "type": "context",
                    "elements": [{
                        "type": "mrkdwn",
                        "text": f"{confidence_emoji} *Draft:* _{response_text}_"
                    }]
                })

        # Show "and X more" if we truncated
        if total_count > len(mentions):
            blocks.append({
                "type": "context",
                "elements": [{
                    "type": "mrkdwn",
                    "text": f"_...and {total_count - len(mentions)} more unanswered mention{'s' if (total_count - len(mentions)) != 1 else ''}_"
                }]
            })

        blocks.append({"type": "divider"})

        return blocks

    def _build_weekly_summary_blocks(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build Slack blocks for weekly summary.

        Args:
            data: Weekly report data

        Returns:
            List of Slack Block Kit blocks
        """
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📈 Weekly Summary - {data.get('date', 'This Week')}",
                    "emoji": True
                }
            },
            {"type": "divider"}
        ]

        # Note: Unanswered @Mentions are sent as separate messages before this

        # Week Overview
        if data.get('overview'):
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*📋 Week at a Glance*\n{data['overview']}"
                }
            })
            blocks.append({"type": "divider"})

        # High-Level Accomplishments
        if data.get('major_accomplishments'):
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*🏆 Major Accomplishments*"
                }
            })

            for item in data['major_accomplishments'][:8]:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"• {item}"
                    }
                })

            blocks.append({"type": "divider"})

        # Team Performance Summary
        if data.get('team_summary'):
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*👥 Team Summary*\n" + data['team_summary']
                }
            })
            blocks.append({"type": "divider"})

        # Next Week Focus
        if data.get('next_week_focus'):
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*🎯 Focus Areas for Next Week*"
                }
            })

            for item in data['next_week_focus'][:5]:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"• {item}"
                    }
                })

            blocks.append({"type": "divider"})

        # Friday's Completed Tasks (show daily brief section on Fridays)
        if data.get('completed_tasks'):
            completed_by_person = {}
            for task in data['completed_tasks']:
                assignee = task.get('assignee', 'Unassigned')
                if assignee not in completed_by_person:
                    completed_by_person[assignee] = []
                completed_by_person[assignee].append(task)

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🎯 Friday's Completed Tasks* ({len(data['completed_tasks'])} tasks)"
                }
            })

            for person, tasks in completed_by_person.items():
                task_list = '\n'.join([
                    f"  • <https://app.asana.com/0/0/{t['gid']}|{t['name']}>"
                    for t in tasks[:20]
                ])
                if len(tasks) > 20:
                    task_list += f"\n  • _...and {len(tasks) - 20} more_"

                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{person}* ({len(tasks)} tasks)\n{task_list}"
                    }
                })

        # Footer
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"_Generated at {data.get('timestamp', 'now')}_"
                }
            ]
        })

        return blocks
