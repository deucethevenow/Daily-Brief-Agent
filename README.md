# Daily Brief Agent

An intelligent multi-agent system that automatically reviews your daily meetings, extracts action items, and provides daily summaries of team progress and overdue tasks. Action items are intelligently suggested with full context, giving you control over what gets added to Asana.

## Features

- 🎙️ **Meeting Analysis**: Automatically processes meeting transcripts from Fireflies (via Airtable)
- 🤖 **AI-Powered Extraction**: Uses Claude to intelligently extract action items from meetings
- 💡 **Smart Suggestions**: Suggests action items from meetings for your review (optional auto-creation)
- 📊 **Daily Reports**: Summarizes completed tasks and overdue items by team member
- 📈 **Weekly Summaries**: Every Friday, provides high-level insights on team progress
- 💬 **Slack Delivery**: Sends formatted reports directly to your Slack channel
- ⏰ **Automated Scheduling**: Runs automatically at 4pm MT every day

## Architecture

The system uses a multi-agent architecture with specialized agents:

- **MeetingAnalyzerAgent**: Uses Claude to extract action items from meeting transcripts
- **AsanaSummaryAgent**: Uses Claude to generate intelligent summaries of team activity
- **DailyBriefCoordinator**: Orchestrates all agents and integrations

### Data Flow

```
Fireflies → Make.com → Airtable
                          ↓
               DailyBriefCoordinator
                    ↓         ↓
          MeetingAnalyzer  AsanaSummary
                    ↓         ↓
                  Asana    Slack
```

## Prerequisites

- Python 3.8 or higher
- API credentials for:
  - Anthropic Claude API
  - Airtable
  - Asana
  - Slack

## Installation

1. **Clone or navigate to the project directory:**
   ```bash
   cd daily-brief-agent
   ```

2. **Create a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```

   Edit `.env` with your API keys and configuration (see Configuration section below).

## Configuration

### Required API Keys

1. **Anthropic Claude API Key**
   - Get from: https://console.anthropic.com/
   - Add to `.env`: `ANTHROPIC_API_KEY=your_key_here`

2. **Airtable Configuration**
   - Personal Access Token: https://airtable.com/create/tokens
   - Find Base ID: Open your base, URL format is `airtable.com/[BASE_ID]/...`
   - Table Name: The name of your table storing meeting data
   - Add to `.env`:
     ```
     AIRTABLE_API_KEY=your_token_here
     AIRTABLE_BASE_ID=appXXXXXXXXXXXXXX
     AIRTABLE_TABLE_NAME=Meetings
     ```

3. **Asana Configuration**
   - Personal Access Token: https://app.asana.com/0/my-apps
   - Workspace GID: Go to Asana, Settings → Organization → Copy workspace ID
   - Add to `.env`:
     ```
     ASANA_ACCESS_TOKEN=your_token_here
     ASANA_WORKSPACE_GID=your_workspace_gid
     ```

4. **Slack Configuration**
   - Create a Slack App: https://api.slack.com/apps
   - Add Bot Token Scopes: `chat:write`, `chat:write.public`
   - Install app to workspace and copy Bot User OAuth Token
   - Get Channel ID: Right-click channel → View channel details → Copy ID
   - Add to `.env`:
     ```
     SLACK_BOT_TOKEN=xoxb-your-token-here
     SLACK_CHANNEL_ID=C01234567
     ```

### Airtable Schema

Your Airtable table should have these fields (adjust field names in `airtable_client.py` if different):

- `Date` or `Meeting Date` or `Created` (Date field)
- `Title` or `Meeting Title` (Single line text)
- `Transcript` or `Notes` (Long text)
- `Summary` (Long text, optional)
- `Participants` or `Attendees` (Multiple select or text, optional)
- `Duration` (Number, optional)

## Usage

### Test Connections

Before running the full system, test your API connections:

```bash
python coordinator.py
```

This will:
1. Validate your configuration
2. Test all API connections
3. Run a single daily brief immediately

### Run Once

To run the daily brief once manually:

```bash
python coordinator.py
```

### Start the Scheduler

To run the daily brief automatically at 4pm MT every day:

```bash
python scheduler.py
```

The scheduler will:
- Run every day at 4:00 PM Mountain Time
- On Fridays, generate a weekly summary instead of daily brief
- Log all activity to `logs/` directory
- Continue running until stopped with Ctrl+C

### Keep Running in Background

#### Option 1: Using nohup (Linux/Mac)
```bash
nohup python scheduler.py > scheduler.log 2>&1 &
```

#### Option 2: Using screen (Linux/Mac)
```bash
screen -S daily-brief
python scheduler.py
# Press Ctrl+A, then D to detach
# Reattach with: screen -r daily-brief
```

#### Option 3: Using launchd (Mac) - Recommended for production

Create a launch agent (example provided in `docs/setup_launchd.md`).

#### Option 4: Using systemd (Linux) - Recommended for production

Create a systemd service (example provided in `docs/setup_systemd.md`).

## Project Structure

```
daily-brief-agent/
├── agents/
│   ├── meeting_analyzer.py      # Extracts action items from meetings
│   └── asana_summary_agent.py   # Generates task summaries
├── integrations/
│   ├── airtable_client.py       # Fetches meeting data
│   ├── asana_client.py          # Manages Asana tasks
│   └── slack_client.py          # Sends Slack messages
├── utils/
│   └── logger.py                # Logging configuration
├── logs/                        # Daily log files
├── coordinator.py               # Main orchestrator
├── scheduler.py                 # Scheduling system
├── config.py                    # Configuration management
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment template
└── README.md                    # This file
```

## Daily Brief Content

### Weekday (Monday-Thursday) Report

The daily brief includes:
- 💡 **Suggested Action Items**: AI-extracted action items from meetings with full context for your review
- 🎯 **Tasks Completed Today**: Grouped by team member
- ⚠️ **Overdue Tasks**: Grouped by team member with days overdue
- 💡 **AI Insights**: Patterns, highlights, and recommendations

### Friday Weekly Summary

The weekly summary includes:
- 📋 **Week at a Glance**: Overview of the week's activity
- 🏆 **Major Accomplishments**: High-level wins and completed work
- 👥 **Team Summary**: Overall team performance, top contributors, and productivity patterns
- 🎯 **Next Week Focus**: Suggested priorities for the coming week based on patterns and overdue items

### Example: Suggested Action Items

Action items appear in your Slack report like this:

```
💡 Suggested Action Items from Meetings (3 total)
Review these and create tasks in Asana as needed

• Follow up with client on Q4 proposal
  Discuss pricing options and timeline for the Q4 implementation project
  👤 John | 📅 Due: 2024-12-15 | 🔴 High
  From: Client Strategy Meeting

• Update pricing page with new tiers
  Add the enterprise tier and update feature comparison table
  👤 Sarah | 🟡 Medium
  From: Product Review

• Schedule team offsite planning session
  Find dates in January and book venue for 2-day planning session
  👤 Unassigned | 🟢 Low
  From: Leadership Sync
```

Each action item includes:
- **Title**: Clear, actionable description
- **Description**: Full context from the meeting
- **Assignee**: Person mentioned (if any)
- **Due Date**: If mentioned in the meeting
- **Priority**: High/Medium/Low based on context
- **Source**: Which meeting it came from

## Customization

### Action Item Management

By default, action items are **suggested** in your daily report for manual review. This gives you control and lets you verify quality.

**Filtering to Your Action Items:**

The system will only show action items assigned to you (based on `YOUR_NAME` in `.env`). Action items assigned to other team members are filtered out, so you only see what's relevant to you.

Items shown:
- ✅ Action items assigned to your name (e.g., "Deuce Thevenow")
- ✅ Unassigned action items (so you can claim them if relevant)
- ❌ Action items assigned to other team members (filtered out)

**To configure your name:**

Edit your `.env` file:
```
YOUR_NAME=Deuce Thevenow
```

Make sure it matches how your name typically appears in meeting transcripts.

**To enable automatic task creation:**

1. Edit your `.env` file:
   ```
   AUTO_CREATE_TASKS=true
   ```

2. Restart the scheduler

When enabled, tasks will be automatically created in Asana (still filtered to only your action items) with:
- Title and description from the meeting
- Assigned person (if mentioned)
- Due date (if mentioned)
- Link back to the source meeting

**Recommendation**: Keep it disabled initially until you're confident in the extraction quality, then enable if desired.

### Adjusting Field Names

If your Airtable uses different field names, edit `integrations/airtable_client.py`:

```python
# Around line 40-50
meeting_date_str = fields.get('Date') or fields.get('Your_Date_Field')
```

### Changing Run Time

Edit `config.py`:

```python
DAILY_RUN_TIME = "16:00"  # Change to desired time (24-hour format)
```

### Customizing Report Format

Edit the Slack blocks in `integrations/slack_client.py` methods:
- `_build_daily_brief_blocks()` for daily reports
- `_build_weekly_summary_blocks()` for weekly summaries

## Troubleshooting

### Check Logs

Logs are stored in `logs/daily_brief_YYYYMMDD.log`:

```bash
tail -f logs/daily_brief_*.log
```

### Common Issues

1. **"Missing required environment variables"**
   - Ensure all variables in `.env` are set
   - Check `.env` file is in the project root

2. **Airtable: No meetings found**
   - Verify AIRTABLE_BASE_ID and AIRTABLE_TABLE_NAME
   - Check that your table has a Date field with today's date
   - Adjust field name mapping in `airtable_client.py`

3. **Asana: Tasks not created**
   - Verify ASANA_ACCESS_TOKEN has write permissions
   - Check ASANA_WORKSPACE_GID is correct
   - Review logs for specific error messages

4. **Slack: Message not sent**
   - Verify bot has `chat:write` scope
   - Ensure bot is added to the target channel
   - Check SLACK_CHANNEL_ID is correct

5. **Claude API errors**
   - Verify ANTHROPIC_API_KEY is valid
   - Check your API usage limits
   - Review rate limiting in logs

### Testing Individual Components

Test Airtable connection:
```python
from integrations import AirtableClient
client = AirtableClient()
meetings = client.get_today_meetings()
print(f"Found {len(meetings)} meetings")
```

Test Asana connection:
```python
from integrations import AsanaClient
client = AsanaClient()
projects = client.get_all_projects()
print(f"Found {len(projects)} projects")
```

Test Slack connection:
```python
from integrations import SlackClient
client = SlackClient()
client.send_message("Test message from Daily Brief Agent")
```

## Security Notes

- Never commit your `.env` file to version control
- Store API keys securely
- Rotate API keys periodically
- Use read-only tokens where possible (e.g., Airtable)
- Review Slack bot permissions regularly

## License

This project is provided as-is for your personal or organizational use.

## Support

For issues or questions:
1. Check the logs in `logs/` directory
2. Review the troubleshooting section above
3. Verify all API credentials are correct
4. Test individual components as shown above

## Future Enhancements

Potential improvements:
- Add support for multiple Slack channels
- Implement email delivery option
- Add web dashboard for viewing reports
- Support for more meeting platforms (Zoom, Google Meet)
- Custom action item assignment rules
- Integration with other project management tools
- Sentiment analysis of meetings
- Automated follow-up reminders
