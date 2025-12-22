# Chief of Staff Agent - Key Learnings from Daily Brief Agent

This document captures architectural patterns, code snippets, and lessons learned from the `daily-brief-agent` project that can be applied to building a Chief of Staff agent.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Extracting Information from Call Transcripts](#extracting-information-from-call-transcripts)
3. [Querying Asana Efficiently](#querying-asana-efficiently)
4. [AI-Powered Task Extraction & Suggestions](#ai-powered-task-extraction--suggestions)
5. [Generating Intelligent Summaries](#generating-intelligent-summaries)
6. [Error Handling & Resilience](#error-handling--resilience)
7. [Configuration Best Practices](#configuration-best-practices)
8. [Slack Message Formatting](#slack-message-formatting)
9. [Gotchas & Lessons Learned](#gotchas--lessons-learned)

---

## Architecture Overview

### Multi-Agent Coordinator Pattern

The system uses a **coordinator pattern** where a central orchestrator manages multiple specialized agents:

```python
class ChiefOfStaffCoordinator:
    """Main coordinator that orchestrates all subagents and integrations."""

    def __init__(self):
        # Initialize integrations (external APIs)
        self.airtable = AirtableClient()
        self.asana = AsanaClient()
        self.slack = SlackClient()

        # Initialize AI agents (Claude-powered)
        self.meeting_analyzer = MeetingAnalyzerAgent()
        self.asana_summary_agent = AsanaSummaryAgent()
```

### Why This Pattern Works

1. **Separation of Concerns** - Each agent has a single responsibility
2. **Error Isolation** - Failures in one agent don't crash the entire system
3. **Testability** - Each component can be tested independently
4. **Extensibility** - Easy to add new agents (e.g., EmailAgent, CalendarAgent)

### Suggested Agent Types for Chief of Staff

| Agent | Responsibility |
|-------|----------------|
| MeetingAnalyzerAgent | Extract action items, decisions, and key points from transcripts |
| TaskPrioritizationAgent | Analyze workload and suggest task priorities |
| FollowUpAgent | Track commitments and generate follow-up reminders |
| WeeklyPlannerAgent | Create weekly plans based on upcoming meetings and deadlines |
| DelegationAgent | Suggest task assignments based on team capacity |

---

## Extracting Information from Call Transcripts

### Data Source: Airtable (via Make.com webhook from Fireflies)

The meeting data comes from Fireflies transcripts stored in Airtable with this structure:

```python
meeting_data = {
    'id': record['id'],
    'title': fields.get('Title', 'Untitled Meeting'),
    'date': fields.get('Created'),  # ISO format datetime
    'transcript': fields.get('Text', ''),  # Full transcript
    'summary': fields.get('Summary', ''),  # Fireflies-generated summary
    'participants': fields.get('Participants', ''),
    'host': fields.get('Host Name', ''),
    'duration': fields.get('Duration (in seconds)', 0),
}
```

### Fetching Meetings from Airtable

```python
from pyairtable import Api
from datetime import datetime
import pytz

class AirtableClient:
    def __init__(self):
        self.api = Api(AIRTABLE_API_KEY)
        self.table = self.api.table(BASE_ID, TABLE_NAME)

    def get_today_meetings(self) -> List[Dict]:
        """Fetch meetings from today where user was involved."""
        timezone = pytz.timezone('America/Denver')
        today = datetime.now(timezone).date()
        user_email = 'your-email@company.com'

        all_records = self.table.all()
        today_meetings = []

        for record in all_records:
            fields = record['fields']

            # Filter by source type
            if fields.get('Source Material') != 'Fireflies Call':
                continue

            # Filter by user involvement
            host = fields.get('Host Name', '')
            participants = fields.get('Participants', '')
            if user_email not in host and user_email not in participants:
                continue

            # Filter by date
            date_str = fields.get('Created')
            if date_str:
                meeting_date = datetime.fromisoformat(
                    date_str.replace('Z', '+00:00')
                ).astimezone(timezone).date()

                if meeting_date == today:
                    today_meetings.append({
                        'id': record['id'],
                        'title': fields.get('Title'),
                        'transcript': fields.get('Text', ''),
                        'summary': fields.get('Summary', ''),
                        # ... other fields
                    })

        return today_meetings
```

### AI-Powered Transcript Analysis

The key insight: **Use structured JSON prompts** to get consistent, parseable output from Claude.

```python
from anthropic import Anthropic

class MeetingAnalyzerAgent:
    def __init__(self):
        self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.model = "claude-sonnet-4-5-20250929"

    def analyze_meeting(self, meeting_data: Dict) -> List[Dict]:
        """Extract action items from a single meeting."""

        content = f"""Meeting Title: {meeting_data.get('title')}

Meeting Summary:
{meeting_data.get('summary', '')}

Meeting Transcript:
{meeting_data.get('transcript', '')}
"""

        prompt = """You are an expert assistant that analyzes meeting transcripts and extracts action items.

Review the meeting content and identify ALL action items. An action item is any task, follow-up, or commitment that someone agreed to do.

For each action item, provide:
1. A clear, concise title (max 100 characters)
2. A detailed description with context from the meeting
3. The person assigned to complete it (if mentioned, otherwise "Unassigned")
4. A suggested due date if mentioned (format: YYYY-MM-DD), otherwise null

Return your response as a JSON array:
[
  {
    "title": "Action item title",
    "description": "Detailed description with context",
    "assignee": "Person's name or 'Unassigned'",
    "due_date": "YYYY-MM-DD or null",
    "priority": "high/medium/low"
  }
]

If no action items, return: []

IMPORTANT: Only return the JSON array, no additional text."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{"role": "user", "content": f"{prompt}\n\n{content}"}]
        )

        response_text = response.content[0].text.strip()

        # Handle markdown code blocks
        if response_text.startswith('```'):
            response_text = response_text.split('```')[1]
            if response_text.startswith('json'):
                response_text = response_text[4:]
            response_text = response_text.strip()

        action_items = json.loads(response_text)

        # Add meeting context to each item
        for item in action_items:
            item['meeting_title'] = meeting_data.get('title')
            item['meeting_date'] = meeting_data.get('date')

        return action_items
```

### Batch Analysis for Better Context

When analyzing multiple meetings, **batch them together** for better deduplication and context:

```python
def batch_analyze_with_context(self, meetings: List[Dict]) -> Dict:
    """Analyze multiple meetings together for deduplication."""

    # Build combined content
    meetings_content = []
    for i, meeting in enumerate(meetings, 1):
        meetings_content.append(f"""
=== Meeting {i} ===
Title: {meeting.get('title')}
Date: {meeting.get('date')}
Participants: {meeting.get('participants', 'Not specified')}

Summary: {meeting.get('summary', 'No summary')}

Transcript:
{meeting.get('transcript', 'No transcript')}
""")

    combined = '\n\n'.join(meetings_content)

    prompt = """Analyze today's meetings to extract action items and insights.

1. Extract ALL unique action items across all meetings
2. Deduplicate any repeated or similar action items
3. Identify key themes and priorities

Return JSON:
{
  "action_items": [...],
  "key_themes": ["theme1", "theme2"],
  "summary": "Brief summary of today's meetings"
}"""

    # ... Claude API call with max_tokens=8192 for batch analysis
```

---

## Querying Asana Efficiently

### Critical Optimization: Query by Assignee, Not Project

**The Problem:** Querying all projects (100+) causes rate limiting and slow performance.

**The Solution:** Query by team member assignee (5 calls instead of 100+).

```python
import asana

class AsanaClient:
    def __init__(self):
        config = asana.Configuration()
        config.access_token = ASANA_ACCESS_TOKEN
        self.api_client = asana.ApiClient(config)
        self.tasks_api = asana.TasksApi(self.api_client)
        self.users_api = asana.UsersApi(self.api_client)
        self.workspace_gid = WORKSPACE_GID

    def get_overdue_tasks(self) -> List[Dict]:
        """Get overdue tasks for tracked team members."""

        team_members = ['Deuce Thevenow', 'Ian Hong', 'Ines Pagliara']
        today = datetime.now(timezone).date()

        # Get users in workspace
        users = self.users_api.get_users_for_workspace(self.workspace_gid, opts={})

        # Map names to GIDs
        team_user_gids = {}
        for user in users:
            if user.get('name') in team_members:
                team_user_gids[user['name']] = user['gid']

        overdue_tasks = []

        # Query each team member (5 API calls, not 100+)
        for name, user_gid in team_user_gids.items():
            tasks = self.tasks_api.get_tasks(opts={
                'assignee': user_gid,
                'workspace': self.workspace_gid,
                'completed': False,
                'opt_fields': 'name,completed,completed_at,due_on,created_at,projects,projects.name'
            })

            for task in tasks:
                # IMPORTANT: Use completed_at, not completed boolean
                if task.get('completed_at') is not None:
                    continue  # Skip completed tasks

                if task.get('due_on'):
                    due_date = datetime.strptime(task['due_on'], '%Y-%m-%d').date()

                    if due_date < today:
                        days_overdue = (today - due_date).days

                        project_name = 'No Project'
                        if task.get('projects'):
                            project_name = task['projects'][0].get('name', 'No Project')

                        overdue_tasks.append({
                            'gid': task['gid'],
                            'name': task['name'],
                            'due_on': task['due_on'],
                            'days_overdue': days_overdue,
                            'assignee': name,
                            'project': project_name,
                        })

        return overdue_tasks
```

### Task Age Filtering

Filter out ancient overdue tasks to focus on actionable items:

```python
# Only show tasks created in last 45 days
age_limit_days = 45
age_limit_cutoff = today - timedelta(days=age_limit_days)

if task.get('created_at'):
    created_at = datetime.fromisoformat(task['created_at'].replace('Z', '+00:00'))
    created_date = created_at.date()

    if created_date >= age_limit_cutoff:
        # Include this task
        overdue_tasks.append(task_data)
```

### Creating Tasks in Asana

```python
def create_task(self, title: str, notes: str,
                assignee_email: str = None,
                due_date: str = None) -> Dict:
    """Create a new task in Asana."""

    task_data = {
        'name': title,
        'notes': notes,
        'workspace': self.workspace_gid,
    }

    if due_date:
        task_data['due_on'] = due_date  # Format: YYYY-MM-DD

    # Look up assignee by email
    if assignee_email:
        users = self.users_api.get_users_for_workspace(self.workspace_gid, opts={})
        user = next((u for u in users if u.get('email') == assignee_email), None)
        if user:
            task_data['assignee'] = user['gid']

    result = self.tasks_api.create_task({'data': task_data})
    return result
```

---

## AI-Powered Task Extraction & Suggestions

### Filtering Action Items by Relevance

You can filter action items to show only those relevant to a specific user:

```python
def filter_action_items_for_user(action_items: List[Dict], user_name: str, user_email: str) -> List[Dict]:
    """Filter to show only action items relevant to the user."""

    filtered = []
    user_first_name = user_name.split()[0].lower() if user_name else ''

    for item in action_items:
        assignee = item.get('assignee', '').lower()

        # Match on full name, first name, email, or unassigned
        if (user_name.lower() in assignee or
            user_first_name in assignee or
            user_email.lower() in assignee or
            assignee in ['unassigned', 'owner', '']):
            filtered.append(item)

    return filtered
```

### Token Management for Large Datasets

When analyzing many tasks, limit the dataset to stay within Claude's token limits:

```python
def generate_summary(self, overdue_tasks: List[Dict]) -> Dict:
    """Generate summary, limiting to top 50 tasks to avoid token limits."""

    # Sort by most overdue first
    sorted_tasks = sorted(
        overdue_tasks,
        key=lambda x: x.get('days_overdue', 0),
        reverse=True
    )

    # Limit to top 50 most critical
    task_sample = sorted_tasks[:50]

    # Prepare minimal data for Claude (reduce token usage)
    data_summary = {
        'total_overdue_count': len(overdue_tasks),
        'sample_count': len(task_sample),
        'overdue_tasks_sample': [
            {
                'name': t['name'],
                'assignee': t['assignee'],
                'project': t['project'],
                'days_overdue': t['days_overdue']
            }
            for t in task_sample
        ]
    }

    # Now call Claude with reduced token usage
    # max_tokens=2048 is usually sufficient for summaries
```

---

## Generating Intelligent Summaries

### Daily Summary Prompt

```python
prompt = """You are a team productivity analyst. Review the daily Asana task data.

NOTE: You're seeing a sample of the most overdue tasks (up to 50) when the total is large.

Analyze to:
1. Summarize team productivity (what was accomplished)
2. Identify concerning patterns (team members with many overdue items)
3. Highlight notable accomplishments
4. Provide one actionable recommendation

Return JSON:
{
  "overview": "Brief overview paragraph (2-3 sentences)",
  "team_highlights": ["Highlight 1", "Highlight 2"],
  "concerns": ["Concern 1", "Concern 2"],
  "recommendation": "One actionable recommendation"
}

Keep it concise and actionable. Focus on patterns, not listing every task.
IMPORTANT: Only return the JSON object, no additional text."""
```

### Weekly Summary Prompt

```python
prompt = """You are a team productivity analyst creating a weekly executive summary.

Generate:
1. High-level overview of the week (2-3 sentences)
2. Major accomplishments (3-5 bullet points)
3. Team performance summary (productivity, top contributors, patterns)
4. Key focus areas for next week based on overdue items

Return JSON:
{
  "overview": "Executive overview paragraph",
  "major_accomplishments": ["Accomplishment 1", "Accomplishment 2"],
  "team_summary": "Brief team performance paragraph",
  "next_week_focus": ["Focus area 1", "Focus area 2"]
}

Focus on strategic insights and high-level accomplishments.
IMPORTANT: Only return the JSON object, no additional text."""
```

### Pattern Analysis

```python
def analyze_task_patterns(self, completed_tasks: List, overdue_tasks: List) -> Dict:
    """Identify patterns in task completion."""

    # Group overdue by person
    overdue_by_person = {}
    for task in overdue_tasks:
        assignee = task.get('assignee', 'Unassigned')
        if assignee not in overdue_by_person:
            overdue_by_person[assignee] = []
        overdue_by_person[assignee].append(task)

    # Flag people with many overdue tasks
    high_overdue = {
        person: len(tasks)
        for person, tasks in overdue_by_person.items()
        if len(tasks) >= 3  # Threshold for concern
    }

    # Get top performers
    completed_counts = {}
    for task in completed_tasks:
        assignee = task.get('assignee', 'Unassigned')
        completed_counts[assignee] = completed_counts.get(assignee, 0) + 1

    top_performers = sorted(
        completed_counts.items(),
        key=lambda x: x[1],
        reverse=True
    )[:5]

    return {
        'high_overdue_members': high_overdue,
        'top_performers': [{'name': n, 'count': c} for n, c in top_performers],
        'total_overdue': len(overdue_tasks),
        'total_completed': len(completed_tasks)
    }
```

---

## Error Handling & Resilience

### Graceful Degradation

Continue the workflow even if one step fails:

```python
def run_workflow(self):
    # Step 1: Fetch meetings
    try:
        meetings = self.airtable.get_today_meetings()
    except Exception as e:
        self._send_error_notification(f"Failed to fetch meetings: {e}")
        return False  # Can't continue without meeting data

    # Step 2: Analyze (can fail gracefully)
    try:
        analysis = self.meeting_analyzer.batch_analyze(meetings)
        action_items = analysis.get('action_items', [])
    except Exception as e:
        self._send_error_notification(f"Analysis failed: {e}")
        action_items = []  # Continue with empty list

    # Step 3: Fetch Asana (can fail gracefully)
    try:
        completed = self.asana.get_completed_tasks_today()
        overdue = self.asana.get_overdue_tasks()
    except Exception as e:
        self._send_error_notification(f"Asana fetch failed: {e}")
        completed, overdue = [], []  # Continue without Asana data

    # Step 4: Send report (always attempt)
    self.slack.send_daily_brief({
        'action_items': action_items,
        'completed_tasks': completed,
        'overdue_tasks': overdue,
    })

    return True
```

### Error Notifications

```python
def _send_error_notification(self, error_message: str):
    """Send error notification to Slack."""
    try:
        self.slack.send_message(
            text="Daily Brief Failed",
            blocks=[
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "Daily Brief Error"}
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"The daily brief failed:\n\n```{error_message}```"
                    }
                }
            ]
        )
    except Exception as e:
        logger.error(f"Failed to send error notification: {e}")
```

### JSON Parsing Safety

Claude sometimes wraps JSON in markdown code blocks:

```python
def parse_claude_json(response_text: str) -> dict:
    """Safely parse JSON from Claude response."""
    text = response_text.strip()

    # Handle markdown code blocks
    if text.startswith('```'):
        text = text.split('```')[1]
        if text.startswith('json'):
            text = text[4:]
        text = text.strip()

    return json.loads(text)
```

---

## Configuration Best Practices

### Environment-Based Config

```python
import os
from pathlib import Path
from dotenv import load_dotenv
import pytz

env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

class Config:
    # Required API keys
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
    AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')
    ASANA_ACCESS_TOKEN = os.getenv('ASANA_ACCESS_TOKEN')
    SLACK_BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN')

    # Optional with defaults
    TIMEZONE = pytz.timezone(os.getenv('TIMEZONE', 'America/Denver'))
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

    # Feature flags
    AUTO_CREATE_TASKS = os.getenv('AUTO_CREATE_TASKS', 'false').lower() == 'true'

    # Team configuration
    _team_str = os.getenv('TEAM_MEMBERS', '')
    TEAM_MEMBERS = [name.strip() for name in _team_str.split(',') if name.strip()]

    # Filtering
    TASK_AGE_LIMIT_DAYS = int(os.getenv('TASK_AGE_LIMIT_DAYS', '45'))

    @classmethod
    def validate(cls):
        """Validate required configuration."""
        required = [
            ('ANTHROPIC_API_KEY', cls.ANTHROPIC_API_KEY),
            ('ASANA_ACCESS_TOKEN', cls.ASANA_ACCESS_TOKEN),
            # ... other required vars
        ]

        missing = [name for name, value in required if not value]

        if missing:
            raise ValueError(f"Missing required env vars: {', '.join(missing)}")

        return True
```

---

## Slack Message Formatting

### Block Kit Structure

```python
def build_daily_brief_blocks(self, data: Dict) -> List[Dict]:
    """Build Slack blocks for daily brief."""

    blocks = [
        # Header
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Daily Brief - {data['date']}",
                "emoji": True
            }
        },
        {"type": "divider"},

        # Section with markdown
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Action Items* ({len(data['items'])} items)"
            }
        },
    ]

    # Add items
    for item in data['items'][:10]:  # Limit for readability
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{item['title']}*\n{item['description']}\n_{item['assignee']}_"
            }
        })

    # Context/footer
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": f"_Generated at {data['timestamp']}_"
        }]
    })

    return blocks
```

### Linking to Asana Tasks

```python
# Create clickable Asana task links
task_link = f"<https://app.asana.com/0/0/{task['gid']}|{task['name']}>"
```

---

## Gotchas & Lessons Learned

### 1. Airtable Field Names Are Exact

```python
# WRONG - won't match
source = fields.get('Source material')

# CORRECT
source = fields.get('Source Material')  # Exact capitalization
```

Also: `"Fireflies Call"` (singular) not `"Fireflies Calls"` (plural).

### 2. Asana Completed Detection

```python
# WRONG - unreliable
is_incomplete = not task.get('completed', False)

# CORRECT - check completed_at timestamp
is_incomplete = task.get('completed_at') is None
```

### 3. Token Limits with Large Datasets

- Claude has a ~200K token context limit
- Analyzing 5,000+ tasks will fail
- **Solution:** Sort by priority, take top 50

### 4. Timezone Handling

```python
import pytz

timezone = pytz.timezone('America/Denver')
now = datetime.now(timezone)  # Always use timezone-aware

# Parse ISO strings correctly
dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
dt = dt.astimezone(timezone)
```

### 5. SSL Certificate Issues on macOS

```python
import ssl
import certifi

ssl_context = ssl.create_default_context(cafile=certifi.where())
client = WebClient(token=SLACK_TOKEN, ssl=ssl_context)
```

### 6. Rate Limiting

- Asana: Query by assignee (5 calls) not by project (100+ calls)
- Add delays between batch operations if needed
- Cache user lookups (GID mappings don't change often)

---

## Extending for Chief of Staff Agent

### Additional Capabilities to Consider

1. **Calendar Integration** - Analyze upcoming meetings to prepare briefings
2. **Email Summarization** - Extract action items from email threads
3. **Priority Scoring** - ML-based priority scoring for tasks
4. **Delegation Suggestions** - Analyze team capacity and suggest task assignments
5. **Meeting Prep** - Generate pre-meeting briefs with relevant context
6. **Weekly Planning** - Create weekly priority lists based on deadlines and importance
7. **Stakeholder Tracking** - Track commitments made to key stakeholders

### Suggested Agent Architecture

```python
class ChiefOfStaffCoordinator:
    def __init__(self):
        # Data sources
        self.calendar = GoogleCalendarClient()
        self.email = GmailClient()
        self.airtable = AirtableClient()
        self.asana = AsanaClient()

        # AI agents
        self.meeting_prep_agent = MeetingPrepAgent()
        self.priority_agent = PriorityAgent()
        self.delegation_agent = DelegationAgent()
        self.briefing_agent = BriefingAgent()

        # Output channels
        self.slack = SlackClient()

    def run_morning_brief(self):
        """Generate morning briefing with today's priorities."""
        pass

    def run_meeting_prep(self, meeting_id: str):
        """Generate prep materials for upcoming meeting."""
        pass

    def run_weekly_planning(self):
        """Generate weekly priority list."""
        pass
```

---

## Quick Start Template

```python
# chief_of_staff/coordinator.py

from datetime import datetime
from typing import Dict, List, Any
from config import Config
from integrations import AirtableClient, AsanaClient, SlackClient
from agents import MeetingAnalyzerAgent, PriorityAgent

class ChiefOfStaffCoordinator:
    def __init__(self):
        Config.validate()

        self.airtable = AirtableClient()
        self.asana = AsanaClient()
        self.slack = SlackClient()

        self.meeting_analyzer = MeetingAnalyzerAgent()
        self.priority_agent = PriorityAgent()

    def run_morning_brief(self) -> bool:
        try:
            # 1. Get today's meetings for prep
            meetings = self.airtable.get_today_meetings()

            # 2. Get current task status
            overdue = self.asana.get_overdue_tasks()
            due_today = self.asana.get_tasks_due_today()

            # 3. Generate priority analysis
            priorities = self.priority_agent.analyze(overdue, due_today, meetings)

            # 4. Send briefing
            self.slack.send_morning_brief({
                'date': datetime.now().strftime('%B %d, %Y'),
                'priorities': priorities,
                'meetings': meetings,
                'due_today': due_today,
            })

            return True

        except Exception as e:
            self._send_error_notification(str(e))
            return False


if __name__ == "__main__":
    coordinator = ChiefOfStaffCoordinator()
    coordinator.run_morning_brief()
```

---

## Dependencies

```txt
# requirements.txt
anthropic>=0.18.0
pyairtable>=2.0.0
asana>=5.0.0
slack-sdk>=3.21.0
python-dotenv>=1.0.0
pytz>=2024.1
schedule>=1.2.0
certifi>=2024.2.2
```

---

*Document generated from daily-brief-agent project analysis*
*Last updated: December 2024*
