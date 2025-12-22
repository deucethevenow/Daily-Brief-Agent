# Setup Checklist

Quick reference guide - see [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed instructions.

## 📋 Pre-Setup

- [ ] Python 3.8+ installed
- [ ] Git clone or download complete
- [ ] Terminal open in project directory

## 🔑 API Keys to Collect

### 1. Anthropic Claude (~5 min)
- [ ] Go to: https://console.anthropic.com/
- [ ] Create account + add payment method
- [ ] Create API key
- [ ] Copy key (starts with `sk-ant-`)
- [ ] Cost: ~$2-3/month

### 2. Airtable (~5 min)
- [ ] Go to: https://airtable.com/create/tokens
- [ ] Create token with `data.records:read` scope
- [ ] Copy token (starts with `pat`)
- [ ] Open your base, copy Base ID from URL (starts with `app`)
- [ ] Note exact table name with meetings

### 3. Asana (~3 min)
- [ ] Go to: https://app.asana.com/0/my-apps
- [ ] Create Personal Access Token
- [ ] Copy token (starts with `1/`)
- [ ] Get Workspace GID from Settings → Organization URL

### 4. Slack (~7 min)
- [ ] Go to: https://api.slack.com/apps
- [ ] Create New App → From Scratch
- [ ] Name: "Daily Brief Agent"
- [ ] Add scopes: `chat:write`, `chat:write.public`
- [ ] Install to workspace
- [ ] Copy Bot User OAuth Token (starts with `xoxb-`)
- [ ] Get your User ID (right-click your name → Copy Member ID)

## 🛠️ Installation

```bash
cd daily-brief-agent

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env from template
cp .env.template .env

# Edit .env with your API keys
nano .env  # or code .env, vim .env, etc.
```

## ✅ Configuration File

Your `.env` should have:

```bash
ANTHROPIC_API_KEY=sk-ant-...        # ✓
AIRTABLE_API_KEY=pat...             # ✓
AIRTABLE_BASE_ID=app...             # ✓
AIRTABLE_TABLE_NAME=Meetings        # ✓
ASANA_ACCESS_TOKEN=1/...            # ✓
ASANA_WORKSPACE_GID=12345...        # ✓
SLACK_BOT_TOKEN=xoxb-...            # ✓
SLACK_CHANNEL_ID=U...               # ✓ (your User ID)
TIMEZONE=America/Denver             # ✓
YOUR_NAME=Deuce Thevenow            # ✓
AUTO_CREATE_TASKS=false             # ✓
```

## 🧪 Testing

- [ ] Run: `python coordinator.py`
- [ ] Check output for ✓ marks
- [ ] Verify Slack test message received
- [ ] Check logs: `tail -f logs/daily_brief_*.log`

## 🚀 Going Live

- [ ] Start scheduler: `python scheduler.py`
- [ ] Verify it says: "Daily brief will run at 16:00 America/Denver"
- [ ] Leave running (or setup as background service)
- [ ] Wait for 4pm MT!

## 🎯 First Day Checklist

After your first 4pm brief:

- [ ] Received Slack message
- [ ] Action items look correct
- [ ] Your name filtering works
- [ ] Completed tasks showing correctly
- [ ] Overdue tasks accurate

## 🔧 Fine-Tuning

After 3-5 days:

- [ ] Review action item extraction quality
- [ ] Adjust `YOUR_NAME` if needed (check logs)
- [ ] Consider enabling `AUTO_CREATE_TASKS` if happy
- [ ] Customize Slack formatting if desired

## 🆘 Troubleshooting

If something doesn't work:

1. Check logs: `tail -f logs/daily_brief_*.log`
2. See [SETUP_GUIDE.md](SETUP_GUIDE.md) troubleshooting section
3. Verify .env file has no typos or extra spaces

## 📊 Verification Commands

```bash
# Test Airtable
python -c "from integrations import AirtableClient; c = AirtableClient(); print(f'Found {len(c.get_today_meetings())} meetings')"

# Test Asana
python -c "from integrations import AsanaClient; c = AsanaClient(); print(f'Found {len(c.get_overdue_tasks())} overdue tasks')"

# Test Slack
python -c "from integrations import SlackClient; c = SlackClient(); c.send_message('Test from Daily Brief Agent! ✓')"

# Full system test
python coordinator.py
```

## 🎉 Done!

Once everything is working:
- Leave `python scheduler.py` running
- First brief arrives at 4pm MT
- Weekly summary on Fridays
- Review and adjust as needed

---

**Time to complete**: ~30-45 minutes (mostly waiting for API approvals)

**Questions?** See [SETUP_GUIDE.md](SETUP_GUIDE.md) or check logs.
