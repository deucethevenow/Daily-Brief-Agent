# Quick Start Guide

Get your Daily Brief Agent up and running in 5 minutes!

## Prerequisites

- Python 3.8+
- API keys ready (see below)

## Step 1: Install Dependencies

```bash
cd daily-brief-agent

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install packages
pip install -r requirements.txt
```

## Step 2: Get Your API Keys

### Anthropic Claude
1. Go to https://console.anthropic.com/
2. Create an API key
3. Copy the key

### Airtable
1. Go to https://airtable.com/create/tokens
2. Create a personal access token with read access
3. Open your Airtable base
4. Copy the Base ID from the URL: `airtable.com/[BASE_ID]/...`
5. Note your table name (e.g., "Meetings")

### Asana
1. Go to https://app.asana.com/0/my-apps
2. Create a Personal Access Token
3. Go to Settings → Organization
4. Copy your Workspace ID

### Slack
1. Go to https://api.slack.com/apps
2. Click "Create New App" → "From scratch"
3. Add Bot Token Scopes:
   - `chat:write`
   - `chat:write.public`
4. Install app to workspace
5. Copy the "Bot User OAuth Token" (starts with `xoxb-`)
6. Right-click your desired channel → "View channel details" → Copy channel ID

## Step 3: Configure

### Option A: Automated Setup (Recommended)
```bash
python setup.py
```

This interactive script will guide you through configuration and test your connections.

### Option B: Manual Setup
```bash
# Copy the template
cp .env.example .env

# Edit with your favorite editor
nano .env  # or vim, code, etc.
```

Fill in all the API keys and IDs.

**Important**: Set `YOUR_NAME` to your name (e.g., "Deuce Thevenow") so the system only shows action items assigned to you, not the entire team.

## Step 4: Test

```bash
# Test all connections and run one brief
python coordinator.py
```

Check your Slack channel for the test message!

## Step 5: Start the Scheduler

```bash
# Run the scheduler
python scheduler.py
```

The agent will now run automatically at 4pm MT every day!

To keep it running in the background:

```bash
# Option 1: nohup
nohup python scheduler.py > scheduler.log 2>&1 &

# Option 2: screen
screen -S daily-brief
python scheduler.py
# Press Ctrl+A, then D to detach
```

## Troubleshooting

### "No meetings found"
- Check your Airtable has entries with today's date
- Verify the Date field name in your table
- Check AIRTABLE_TABLE_NAME matches exactly

### "Asana API error"
- Verify your Personal Access Token is correct
- Check the Workspace GID is correct
- Ensure token has write permissions

### "Slack message not sent"
- Verify bot is added to the channel
- Check bot has `chat:write` scope
- Confirm channel ID is correct

### "Claude API error"
- Verify ANTHROPIC_API_KEY is correct
- Check your API usage/credits
- Ensure you have access to the Claude API

## What to Expect

### Daily (Mon-Thu at 4pm MT)
You'll receive a Slack message with:
- **Suggested action items assigned to you** from today's meetings with full context (action items for other team members are filtered out)
- Tasks completed today (grouped by person)
- Overdue tasks (grouped by person)
- AI-generated insights

**Note**:
- Only action items assigned to you (or unassigned) are shown - you won't see items for other team members
- Action items are suggested by default, not auto-created. This lets you verify quality first.
- To enable auto-creation later, set `AUTO_CREATE_TASKS=true` in `.env`

### Friday (4pm MT)
You'll receive an enhanced weekly summary with:
- Week overview
- Major accomplishments
- Team performance summary (top contributors, patterns)
- Focus areas for next week

## Next Steps

- Review the full README.md for advanced configuration
- Customize Slack message formatting in `integrations/slack_client.py`
- Adjust Airtable field mappings if needed
- Set up system service for production (launchd/systemd)

## Need Help?

1. Check the logs: `tail -f logs/daily_brief_*.log`
2. Review README.md troubleshooting section
3. Test individual components as shown in README.md
