# Troubleshooting Guide - Daily Brief Agent

Quick reference for common issues and their solutions.

---

## 🔍 Quick Diagnostics

### Check if scheduler is running
```bash
ps aux | grep scheduler.py
```

### View recent logs
```bash
tail -50 logs/daily_brief_$(date +%Y%m%d).log
```

### Test all connections
```bash
source venv/bin/activate
python test_connections.py
```

---

## ❌ Common Issues

### "No meetings found today"

**Symptoms**:
- Daily brief shows 0 meetings
- Log says "Found 0 meetings from today"

**Checklist**:
1. ✅ Check Airtable has meetings with today's date
2. ✅ Verify `Source Material` field = "Fireflies Call" (singular, not plural)
3. ✅ Confirm `Created` field has today's date
4. ✅ Check your email (deuce@recess.is) is in `Host Name` OR `Participants`
5. ✅ Verify `Text` field contains the transcript

**How to test**:
```bash
python -c "
from integrations.airtable_client import AirtableClient
client = AirtableClient()
meetings = client.get_today_meetings()
print(f'Found {len(meetings)} meetings')
for m in meetings:
    print(f'  - {m[\"title\"]}: {len(m[\"transcript\"])} chars')
"
```

**Common causes**:
- Wrong field name (check `Text` vs `Transcript`)
- Wrong filter value ("Fireflies calls" vs "Fireflies Call")
- Date parsing issue (check timezone)

---

### "Action items not showing for me"

**Symptoms**:
- Daily brief shows action items for others
- Your action items are missing

**Checklist**:
1. ✅ Check `YOUR_NAME` in `.env` matches transcript exactly
2. ✅ Try first name only: `YOUR_NAME=Deuce`
3. ✅ Check action items aren't assigned to someone else

**How to test**:
```bash
# Check what names appear in action items
python run_for_date.py 2025-10-23
# Look in logs for "assignee" values
```

**Common causes**:
- Name mismatch (transcript says "Deuce" but `.env` has "Deuce Thevenow")
- Action items assigned to others (working as intended)

---

### "Completed tasks showing as overdue"

**Symptoms**:
- Tasks marked complete in Asana appear in overdue list
- Example: "Review CDMX pre-read" (completed Sep 15) shows as overdue

**Solution**:
This was fixed in the latest version. Update your code or verify `asana_client.py` line 283:
```python
if task.get('completed_at') is not None:
    continue  # Skip completed tasks
```

**How to verify it's fixed**:
```bash
python analyze_overdue.py
# Check if count is reasonable (~49 vs 5,756)
```

---

### "Too many overdue tasks (5,000+)"

**Symptoms**:
- Overdue list has thousands of tasks
- Many tasks are years old (3,506 days overdue)

**Solution**:
Adjust age filter in `.env`:
```bash
ASANA_TASK_AGE_LIMIT_DAYS=45  # Only last 45 days
```

**Effect**:
- Before: 5,756 total (includes tasks from 2015)
- After: 49 recent (last 45 days only)

**How to test**:
```bash
python analyze_overdue.py
```

---

### "Scheduler not sending at 4pm"

**Symptoms**:
- No Slack message at 4:00 PM MT
- Scheduler seems to be running

**Checklist**:
1. ✅ Check timezone in `.env`: `TIMEZONE=America/Denver`
2. ✅ Verify current time: `date` (should show MDT/MST)
3. ✅ Check scheduler logs for errors
4. ✅ Confirm scheduler is actually running: `ps aux | grep scheduler.py`

**Common causes**:
- Timezone mismatch (computer vs config)
- Scheduler stopped/crashed
- Permission issues with Slack

---

### "SSL Certificate Error (Slack)"

**Symptoms**:
```
[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed
```

**Solution**:
Already fixed in `slack_client.py`:
```python
import ssl
import certifi
ssl_context = ssl.create_default_context(cafile=certifi.where())
```

**If still occurring**:
```bash
pip install --upgrade certifi
```

---

### "Asana API: Authentication failed"

**Symptoms**:
```
Error: invalid token
```

**Checklist**:
1. ✅ Check token starts with `1/` or `2/` (new format)
2. ✅ Verify no extra spaces in `.env`
3. ✅ Confirm token hasn't expired
4. ✅ Check workspace GID is correct

**How to test**:
```bash
python test_connections.py
```

---

### "Claude API: Invalid API key"

**Symptoms**:
```
authentication_error: invalid x-api-key
```

**Checklist**:
1. ✅ Check key starts with `sk-ant-api03-`
2. ✅ Verify complete key (not truncated)
3. ✅ No extra spaces or quotes in `.env`
4. ✅ Check usage limits at console.anthropic.com

---

### "Team member not found in Asana"

**Symptoms**:
- Log says "Found 4 team members" but you have 5
- Example: "Char Short" not found

**Solution**:
Check exact name spelling in Asana:
1. Go to Asana workspace
2. Check user list for exact name
3. Update `TEAM_MEMBERS` in `.env` to match exactly

**Current status**:
- ✅ Deuce Thevenow
- ✅ Ian Hong
- ✅ Ines Pagliara
- ✅ Recess Accounting
- ❌ Char Short (check if it's "Charlotte Short" or just "Char")

---

### "System running slow (>5 minutes)"

**Symptoms**:
- Coordinator takes forever
- Hangs at "Fetching overdue tasks"

**Causes & Solutions**:

**1. Too many team members**:
```bash
# Each person = 1 Asana API call (~10 seconds)
# 5 people = 50 seconds total
# Solution: This is normal
```

**2. No team members configured**:
```bash
# Falls back to querying ALL projects (100+)
# Solution: Set TEAM_MEMBERS in .env
```

**3. Network issues**:
```bash
# Check internet connection
ping api.asana.com
```

---

### "Friday weekly summary not generating"

**Symptoms**:
- Friday brief looks same as weekday brief
- No "Week at a Glance" section

**How to test**:
```bash
python run_for_date.py 2025-10-24  # Any Friday
```

**Check**:
- Log should say "Friday: True"
- Log should say "Generating weekly summary"

**If not working**:
- Verify `override_date` parameter in `run_daily_brief()`
- Check `today.weekday() == 4` logic

---

## 🔧 Advanced Diagnostics

### Check Airtable field structure
```bash
python -c "
from integrations.airtable_client import AirtableClient
client = AirtableClient()
records = client.table.all(max_records=1)
if records:
    print('Available fields:')
    for key in records[0]['fields'].keys():
        print(f'  - {key}')
"
```

### Check Asana workspace users
```bash
python -c "
from integrations.asana_client import AsanaClient
client = AsanaClient()
users = client.users_api.get_users_for_workspace(client.workspace_gid, opts={})
print('Users in workspace:')
for user in users:
    print(f'  - {user.get(\"name\")}: {user.get(\"email\")}')
"
```

### Test Claude API directly
```bash
python -c "
from anthropic import Anthropic
from config import Config
client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
response = client.messages.create(
    model='claude-3-5-sonnet-20241022',
    max_tokens=100,
    messages=[{'role': 'user', 'content': 'Say hi'}]
)
print(response.content[0].text)
"
```

---

## 📊 Performance Benchmarks

**Normal runtimes**:
- Airtable fetch: 3-4 seconds
- Asana tasks (5 people): 45-60 seconds
- Claude analysis: 10-20 seconds
- Slack delivery: 1-2 seconds
- **Total: 1-2 minutes**

**If taking longer**:
- >2 minutes: Check network
- >5 minutes: Check TEAM_MEMBERS is set
- >10 minutes: Something is wrong - check logs

---

## 🆘 Emergency Procedures

### Stop everything
```bash
# Stop scheduler
pkill -f scheduler.py

# Or if running in foreground
# Press Ctrl+C
```

### Reset and restart
```bash
cd /Users/deucethevenowworkm1/daily-brief-agent
source venv/bin/activate

# Test connections
python test_connections.py

# Run once manually
python coordinator.py

# If successful, restart scheduler
python scheduler.py
```

### Check system resources
```bash
# Check if Python process is hanging
top | grep python

# Check available memory
vm_stat

# Check disk space
df -h
```

---

## 📝 Where to Find Help

1. **Logs**: `logs/daily_brief_*.log`
2. **This file**: Common issues and solutions
3. **README.md**: Configuration and setup
4. **IMPLEMENTATION_NOTES.md**: Detailed technical info
5. **Code comments**: In-line documentation

---

## 🔍 Debugging Checklist

When something's not working:

- [ ] Check logs: `tail -50 logs/daily_brief_*.log`
- [ ] Test connections: `python test_connections.py`
- [ ] Verify `.env` has all required variables
- [ ] Check scheduler is running: `ps aux | grep scheduler.py`
- [ ] Try manual run: `python coordinator.py`
- [ ] Check API rate limits (Asana, Claude)
- [ ] Verify internet connection
- [ ] Restart scheduler if needed

---

**Last Updated**: October 27, 2025
**Status**: Comprehensive troubleshooting guide for all known issues ✅
