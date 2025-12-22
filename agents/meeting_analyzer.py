"""Meeting Analyzer Agent - Extracts action items from meeting transcripts using Claude."""
import json
from typing import List, Dict, Any
from anthropic import Anthropic
from config import Config
from utils import setup_logger

logger = setup_logger(__name__)

# Import here to avoid circular dependency
def send_error_to_slack(error_message: str):
    """Send error notification to Slack."""
    try:
        from integrations.slack_client import SlackClient
        slack = SlackClient()
        slack.send_message(
            text=f"⚠️ Meeting Analysis Error",
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "⚠️ Meeting Analysis Error"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"The meeting analyzer encountered an error:\n\n```{error_message}```"
                    }
                },
                {
                    "type": "context",
                    "elements": [{
                        "type": "mrkdwn",
                        "text": "Check the logs for more details."
                    }]
                }
            ]
        )
    except Exception as e:
        logger.error(f"Failed to send error notification: {e}")


class MeetingAnalyzerAgent:
    """Agent that analyzes meeting transcripts and extracts action items."""

    def __init__(self):
        """Initialize the Meeting Analyzer Agent."""
        self.client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self.model = "claude-sonnet-4-5-20250929"  # Claude Sonnet 4.5 (Sep 2025)
        logger.info("MeetingAnalyzerAgent initialized")

    def analyze_meeting(self, meeting_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyze a single meeting and extract action items.

        Args:
            meeting_data: Meeting data with transcript and metadata

        Returns:
            List of action items with title, description, assignee, and meeting context
        """
        title = meeting_data.get('title', 'Untitled Meeting')
        transcript = meeting_data.get('transcript', '')
        summary = meeting_data.get('summary', '')

        if not transcript and not summary:
            logger.warning(f"No transcript or summary for meeting: {title}")
            return []

        logger.info(f"Analyzing meeting: {title}")

        try:
            # Prepare the content for Claude
            content = f"""Meeting Title: {title}

Meeting Summary:
{summary}

Meeting Transcript:
{transcript}
"""

            prompt = """You are an expert assistant that analyzes meeting transcripts and extracts action items.

Review the meeting content provided and identify ALL action items that need to be completed. An action item is any task, follow-up, or commitment that someone agreed to do.

For each action item, provide:
1. A clear, concise title (max 100 characters)
2. A detailed description with context from the meeting
3. The person assigned to complete it (if mentioned, otherwise use "Owner" or "Unassigned")
4. A suggested due date if mentioned (format: YYYY-MM-DD), otherwise null

Return your response as a JSON array of action items. Each item should have this structure:
{
  "title": "Action item title",
  "description": "Detailed description with context",
  "assignee": "Person's name or 'Unassigned'",
  "due_date": "YYYY-MM-DD or null",
  "priority": "high/medium/low"
}

If there are no action items, return an empty array: []

IMPORTANT: Only return the JSON array, no additional text or explanation."""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[
                    {"role": "user", "content": f"{prompt}\n\n{content}"}
                ]
            )

            # Extract the text response
            response_text = response.content[0].text.strip()

            # Parse JSON response
            # Handle cases where Claude might wrap JSON in markdown code blocks
            if response_text.startswith('```'):
                # Extract JSON from code block
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            action_items = json.loads(response_text)

            # Add meeting context to each action item
            for item in action_items:
                item['meeting_title'] = title
                item['meeting_date'] = meeting_data.get('date', '')

            logger.info(f"Extracted {len(action_items)} action items from meeting: {title}")
            return action_items

        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse Claude response as JSON for meeting '{title}': {e}"
            logger.error(error_msg)
            logger.debug(f"Response text: {response_text}")
            send_error_to_slack(f"{error_msg}\n\nThis meeting's action items were not extracted.")
            return []
        except Exception as e:
            error_msg = f"Error analyzing meeting '{title}': {e}"
            logger.error(error_msg)
            send_error_to_slack(f"{error_msg}\n\nThis meeting's action items were not extracted.")
            return []

    def analyze_meetings(self, meetings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze multiple meetings and extract all action items.

        Args:
            meetings: List of meeting data dictionaries

        Returns:
            Combined list of all action items from all meetings
        """
        logger.info(f"Analyzing {len(meetings)} meetings")

        all_action_items = []

        for meeting in meetings:
            action_items = self.analyze_meeting(meeting)
            all_action_items.extend(action_items)

        logger.info(f"Total action items extracted: {len(all_action_items)}")
        return all_action_items

    def batch_analyze_with_context(self, meetings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze multiple meetings together for better context and deduplication.

        Args:
            meetings: List of meeting data dictionaries

        Returns:
            Dictionary with action items and analysis summary
        """
        if not meetings:
            return {'action_items': [], 'summary': 'No meetings to analyze'}

        logger.info(f"Batch analyzing {len(meetings)} meetings with context")

        try:
            # Build combined content
            meetings_content = []
            for i, meeting in enumerate(meetings, 1):
                meetings_content.append(f"""
=== Meeting {i} ===
Title: {meeting.get('title', 'Untitled')}
Date: {meeting.get('date', 'Unknown')}
Participants: {', '.join(meeting.get('participants', [])) if meeting.get('participants') else 'Not specified'}

Summary: {meeting.get('summary', 'No summary')}

Transcript:
{meeting.get('transcript', 'No transcript available')}
""")

            combined_content = '\n\n'.join(meetings_content)

            prompt = """You are an expert assistant analyzing today's meetings to extract action items and provide insights.

Review all the meetings provided and:
1. Extract ALL unique action items across all meetings
2. Deduplicate any repeated or similar action items
3. Identify key themes and priorities from today's meetings

For each action item, provide:
{
  "title": "Action item title",
  "description": "Detailed description with context",
  "assignee": "Person's name or 'Unassigned'",
  "due_date": "YYYY-MM-DD or null",
  "priority": "high/medium/low",
  "meeting_title": "Which meeting this came from"
}

Return a JSON object with this structure:
{
  "action_items": [...array of action items...],
  "key_themes": ["theme1", "theme2", ...],
  "summary": "Brief summary of today's meetings and action items"
}

IMPORTANT: Only return the JSON object, no additional text."""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=8192,
                messages=[
                    {"role": "user", "content": f"{prompt}\n\n{combined_content}"}
                ]
            )

            response_text = response.content[0].text.strip()

            # Parse JSON response
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            result = json.loads(response_text)

            logger.info(f"Batch analysis complete: {len(result.get('action_items', []))} action items")
            return result

        except Exception as e:
            logger.error(f"Error in batch analysis: {e}")
            # Send error notification to Slack
            send_error_to_slack(f"Batch meeting analysis failed: {str(e)}\n\nFalling back to individual meeting analysis.")
            # Fallback to individual analysis
            return {
                'action_items': self.analyze_meetings(meetings),
                'summary': 'Analysis completed with fallback method',
                'key_themes': []
            }
