# Complete Setup Guide - Getting Your API Keys

This guide walks you through getting every API key needed for the Daily Brief Agent.

## Quick Overview

You need credentials for:
1. ✅ **Anthropic Claude** - AI for extracting action items
2. ✅ **Airtable** - Where your meeting data is stored
3. ✅ **Asana** - Your task management system
4. ✅ **Slack** - Where reports are sent

**Total setup time**: ~20 minutes

---

## 1. Anthropic Claude API Key

### What it's for
Claude analyzes your meeting transcripts and extracts action items with context.

### How to get it

1. **Go to**: https://console.anthropic.com/

2. **Sign up or log in**
   - Use your email
   - You'll need to add a payment method (Claude API is pay-as-you-go)

3. **Create an API key**
   - Click "API Keys" in the left sidebar
   - Click "Create Key"
   - Give it a name: "Daily Brief Agent"
   - Copy the key (starts with `sk-ant-...`)

4. **Pricing info**
   - Claude Sonnet: ~$3 per million input tokens, ~$15 per million output tokens
   - **Your estimated cost**: ~$0.05-0.10 per day ($1.50-3/month)
   - Based on analyzing 2-3 meetings daily

5. **Save this**
   ```
   ANTHROPIC_API_KEY=sk-ant-api03-...
   ```

---

## 2. Airtable Credentials

### What it's for
Airtable stores your Fireflies meeting transcripts (via Make.com webhook).

### How to get it

#### Step A: Get your Personal Access Token

1. **Go to**: https://airtable.com/create/tokens

2. **Create a token**
   - Click "Create new token"
   - Name: "Daily Brief Agent"
   - Scopes needed:
     - ✅ `data.records:read` (read records)
     - ✅ `schema.bases:read` (read base schema)
   - Access: Select your specific base (the one with meetings)
   - Click "Create token"
   - Copy the token (starts with `pat...`)

3. **Save this**
   ```
   AIRTABLE_API_KEY=patXXXXXXXXXXXXXXXX
   ```

#### Step B: Get your Base ID

1. **Open your Airtable base** (the one with meeting data)

2. **Look at the URL**
   ```
   https://airtable.com/appXXXXXXXXXXXXXX/tblYYYYYYYYYYYYYY/...
                        ^^^^^^^^^^^^^^^^^^
                        This is your Base ID
   ```

3. **Copy the part that starts with `app`**

4. **Save this**
   ```
   AIRTABLE_BASE_ID=appXXXXXXXXXXXXXX
   ```

#### Step C: Get your Table Name

1. **In your Airtable base**, look at the tab names at the bottom

2. **Copy the exact table name** where meetings are stored
   - Common names: "Meetings", "Transcripts", "Fireflies Data"
   - Must match exactly (case-sensitive)

3. **Save this**
   ```
   AIRTABLE_TABLE_NAME=Meetings
   ```

#### Step D: Verify your Airtable structure

Your table should have these fields (names may vary):
- ✅ Date field (for filtering today's meetings)
- ✅ Title/Name field
- ✅ Transcript/Notes field (the actual meeting content)
- Optional: Summary, Participants, Duration

**If your field names are different**, you'll need to adjust them in the code (we'll cover this later).

---

## 3. Asana Credentials

### What it's for
Asana is where your tasks live - the system reads completed/overdue tasks for reporting.

### How to get it

#### Step A: Get Personal Access Token

1. **Go to**: https://app.asana.com/0/my-apps

2. **Create a token**
   - Click "Create New Token"
   - Name: "Daily Brief Agent"
   - Click "Create token"
   - Copy the token (starts with `1/...`)
   - ⚠️ **Store this safely** - you can't see it again!

3. **Save this**
   ```
   ASANA_ACCESS_TOKEN=1/XXXXXXXXXX:YYYYYYYYYYYYYYYY
   ```

#### Step B: Get your Workspace GID

1. **In Asana**, click your profile icon (top right)

2. **Go to**: Settings → Organization

3. **Look in the browser URL**
   ```
   https://app.asana.com/admin/XXXXXXXXXXXX/...
                              ^^^^^^^^^^^^
                              This is your Workspace GID
   ```

   OR

4. **Alternative method** (if URL doesn't show it):
   - We'll detect it automatically during setup
   - The setup script will list your workspaces

5. **Save this**
   ```
   ASANA_WORKSPACE_GID=XXXXXXXXXXXX
   ```

---

## 4. Slack Bot Credentials

### What it's for
Sends your daily brief reports to Slack.

### How to get it

#### Step A: Create a Slack App

1. **Go to**: https://api.slack.com/apps

2. **Click "Create New App"**

3. **Choose "From scratch"**
   - App Name: "Daily Brief Agent"
   - Pick your workspace
   - Click "Create App"

#### Step B: Add Bot Permissions

1. **In your app settings**, go to: **OAuth & Permissions** (left sidebar)

2. **Scroll to "Scopes" → "Bot Token Scopes"**

3. **Click "Add an OAuth Scope"** and add:
   - ✅ `chat:write` - Post messages
   - ✅ `chat:write.public` - Post to channels without joining

4. **Scroll up and click "Install to Workspace"**
   - Click "Allow"

5. **Copy the "Bot User OAuth Token"**
   - Starts with `xoxb-`
   - This appears after installation

6. **Save this**
   ```
   SLACK_BOT_TOKEN=xoxb-XXXXXXXXXXXXX-XXXXXXXXXXXXX-XXXXXXXXXXXXXXXXXXXXXXXX
   ```

#### Step C: Get Channel ID

**Option 1: Direct Message (DM) to yourself**

1. **Open Slack desktop or web**
2. **Right-click on your name** in the sidebar
3. **Copy Member ID** (starts with `U`)
4. This sends reports as a DM to you

```
SLACK_CHANNEL_ID=U01234567AB
```

**Option 2: Send to a specific channel**

1. **Right-click the channel name** in Slack
2. **Select "View channel details"**
3. **Scroll down and copy the Channel ID** (starts with `C`)
4. **Important**: Add the bot to the channel
   - In the channel, type `/invite @Daily Brief Agent`

```
SLACK_CHANNEL_ID=C01234567AB
```

**Recommendation**: Start with DM to yourself for testing.

---

## 5. Additional Configuration

### Your Name (for filtering)

```
YOUR_NAME=Deuce Thevenow
```

This should match how your name appears in meeting transcripts. Common variations:
- Full name: "Deuce Thevenow"
- First name: "Deuce"
- However Fireflies transcribes you

### Timezone

```
TIMEZONE=America/Denver
```

This is Mountain Time. Other common options:
- `America/New_York` - Eastern
- `America/Chicago` - Central
- `America/Los_Angeles` - Pacific
- `America/Phoenix` - Arizona (no DST)

Full list: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones

---

## 6. Create Your .env File

Now let's put it all together:

```bash
cd daily-brief-agent
cp .env.example .env
nano .env  # or use your preferred editor
```

Fill in with all your values:

```bash
# Anthropic Claude API
ANTHROPIC_API_KEY=sk-ant-api03-...

# Airtable Configuration
AIRTABLE_API_KEY=patXXXXXXXXXXXXXXXX
AIRTABLE_BASE_ID=appXXXXXXXXXXXXXX
AIRTABLE_TABLE_NAME=Meetings

# Asana Configuration
ASANA_ACCESS_TOKEN=1/XXXXXXXXXX:YYYYYYYYYYYYYYYY
ASANA_WORKSPACE_GID=XXXXXXXXXXXX

# Slack Configuration
SLACK_BOT_TOKEN=xoxb-XXXXXXXXXXXXX-XXXXXXXXXXXXX-XXXXXXXXXXXXXXXXXXXXXXXX
SLACK_CHANNEL_ID=U01234567AB

# Timezone Configuration
TIMEZONE=America/Denver

# Log Level
LOG_LEVEL=INFO

# Task Management
AUTO_CREATE_TASKS=false

# Your name for filtering action items
YOUR_NAME=Deuce Thevenow
```

---

## 7. Test Your Configuration

Once your `.env` is set up:

```bash
# Install dependencies if you haven't
pip install -r requirements.txt

# Test all connections
python coordinator.py
```

This will:
1. ✅ Validate all your API keys
2. ✅ Test each connection
3. ✅ Run a test daily brief
4. ✅ Send a test message to Slack

**Expected output:**
```
✓ Airtable connection successful
✓ Asana connection successful
✓ Slack connection successful
✓ Claude API connection successful
✓ Daily brief completed successfully!
```

---

## Troubleshooting

### "Missing required environment variables"
- Check that your .env file is in the project root
- Verify no typos in variable names
- Ensure no extra spaces around the `=` sign

### "Airtable connection failed"
- Verify Base ID starts with `app`
- Check token has correct scopes
- Ensure table name matches exactly (case-sensitive)

### "Asana connection failed"
- Verify token starts with `1/`
- Check token hasn't expired
- Ensure workspace GID is correct

### "Slack connection failed"
- Verify token starts with `xoxb-`
- Check bot has required scopes
- If sending to channel, ensure bot is invited to channel

### "No meetings found"
- Check that your Airtable has entries with today's date
- Verify the Date field name matches what the code expects
- Look at logs to see what the system is querying

---

## Security Best Practices

1. ✅ **Never commit .env to git** (already in .gitignore)
2. ✅ **Rotate tokens periodically** (every 90 days)
3. ✅ **Use read-only access where possible** (Airtable)
4. ✅ **Limit Slack bot to specific channels**
5. ✅ **Set up token expiration** in Asana/Airtable if available

---

## Cost Summary

- **Anthropic Claude**: ~$1.50-3/month (pay-as-you-go)
- **Airtable**: Free tier sufficient (1,200 records)
- **Asana**: Use your existing plan
- **Slack**: Free (using bot tokens)

**Total additional cost**: ~$2-3/month for Claude API

---

## Next Steps

Once everything is tested and working:

1. ✅ Start the scheduler: `python scheduler.py`
2. ✅ Wait for 4pm MT for your first real brief
3. ✅ Review the suggestions and adjust YOUR_NAME if needed
4. ✅ After a week, consider enabling AUTO_CREATE_TASKS if desired

---

## Need Help?

If you get stuck:
1. Check the logs: `tail -f logs/daily_brief_*.log`
2. Review the main README.md troubleshooting section
3. Test individual components as shown in README.md

Good luck! 🚀
