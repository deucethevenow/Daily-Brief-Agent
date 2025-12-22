# Daily Brief Agent — SOP & Integration Guide

**Status:** Live

**Owner:** Deuce Thevenow

**Last Updated:** October 27, 2025

**Project Type:** AI-Powered Workflow Automation

**Technologies:** Claude AI, Airtable, Asana, Slack, Python

---

## 1) What this is (non-technical)

The Daily Brief Agent is an automated AI assistant that reviews your day every afternoon and delivers a personalized intelligence report to Slack. It:

1. **Analyzes your meeting transcripts** from Fireflies (stored in Airtable) and extracts action items assigned to you
2. **Tracks your team's tasks** in Asana, showing what was completed today and what's overdue
3. **Generates AI insights** using Claude to summarize patterns, highlight concerns, and recommend next steps
4. **Delivers everything to Slack** at 4pm MT daily (with enhanced weekly summaries on Fridays)

The result: You spend **zero time** manually reviewing meetings or tracking tasks, yet you get a comprehensive daily brief that helps you stay on top of your work.

```mermaid
flowchart LR
    A[Fireflies Transcripts<br/>in Airtable] --> B[Daily Brief Agent<br/>Claude AI Analysis]
    C[Asana Tasks<br/>Team Activity] --> B
    B --> D[Slack Message<br/>4pm MT Daily]

    %% Callouts
    A -.->|Filter: deuce@recess.is involved| A
    C -.->|5 team members tracked| C
    D -.->|Enhanced on Fridays| D

    %% Styling
    classDef ai fill:#E6F7FF,stroke:#91DAFF,color:#083042
    classDef data fill:#FFF7E6,stroke:#FFD591,color:#5A3E00
    class B ai
    class A,C data
```

---

## 2) How the automation works (at a glance)

**In plain English**

Every day at 4pm Mountain Time:

1. **Fetch today's meetings** from Airtable (only Fireflies calls where you were host or participant)
2. **Send transcripts to Claude AI** which extracts action items and identifies who's responsible
3. **Filter to your action items** using smart name matching (matches "Deuce", "Deuce Thevenow", "deuce@recess.is", or "Unassigned")
4. **Fetch Asana data** for your 5 team members (completed tasks today + overdue tasks from last 45 days)
5. **Send to Claude AI again** to analyze task patterns, identify concerns, and generate insights
6. **Post formatted brief to Slack** with all the intelligence gathered

**On Fridays**, the system generates an enhanced weekly summary with:
- Week-at-a-glance metrics (total meetings, total completions)
- Major accomplishments across the team
- Next week's focus areas
- All the standard daily brief sections

---

## 3) System architecture (technical flow)

```mermaid
flowchart TD
    A[Scheduler<br/>APScheduler] -->|4pm MT Daily| B[DailyBriefCoordinator]
    B --> C[AirtableClient<br/>Fetch Meetings]
    B --> D[AsanaClient<br/>Fetch Tasks]
    B --> E[MeetingAnalyzerAgent<br/>Claude AI]
    B --> F[AsanaSummaryAgent<br/>Claude AI]
    B --> G[SlackClient<br/>Post Message]

    C -->|Meetings with transcripts| E
    D -->|Completed + Overdue tasks| F
    E -->|Action items extracted| H[Filter to your items]
    F -->|AI insights generated| I[Format Report]
    H --> I
    I --> G

    G -->|Daily brief| J[#recess-leads Slack]

    style B fill:#f0f9ff,stroke:#a6d8ff
    style E fill:#fff9e6,stroke:#ffd591
    style F fill:#fff9e6,stroke:#ffd591
    style G fill:#e8fff3,stroke:#8bd3a3
```

---

## 4) Configuration variables

| Variable | Purpose | Example Value | Notes |
|----------|---------|---------------|-------|
| **ANTHROPIC_API_KEY** | Claude AI authentication | `sk-ant-api03-xxxxx` | Get from console.anthropic.com |
| **AIRTABLE_API_KEY** | Airtable data access | `pat0bryH0fg80C9Sj.xxxxx` | Personal access token |
| **AIRTABLE_BASE_ID** | Airtable base identifier | `appoVSwfWxFPeflJg` | From Airtable URL |
| **AIRTABLE_TABLE_NAME** | Table with transcripts | `Master Inputs Database` | Exact name match required |
| **ASANA_ACCESS_TOKEN** | Asana task access | `2/21487277608513/xxxxx` | Supports 1/ and 2/ formats |
| **ASANA_WORKSPACE_GID** | Asana workspace ID | `21487286163067` | From Asana settings |
| **SLACK_BOT_TOKEN** | Slack posting permission | `xoxb-6521296996-xxxxx` | From Slack app settings |
| **SLACK_CHANNEL_ID** | Where to post briefs | `C09NJKPRR7D` | Channel ID from Slack |
| **YOUR_NAME** | Filter action items | `Deuce Thevenow` | For personal filtering |
| **TEAM_MEMBERS** | Comma-separated list | `Deuce Thevenow,Ian Hong,...` | Who to track in Asana |
| **ASANA_TASK_AGE_LIMIT_DAYS** | Filter old tasks | `45` | Only show tasks created in last N days (0 = show all) |
| **AUTO_CREATE_TASKS** | Auto-add to Asana | `false` | Set to `true` to auto-create action items |
| **TIMEZONE** | Scheduling timezone | `America/Denver` | Mountain Time |
| **DAILY_BRIEF_TIME** | When to run | `16:00` | 4pm MT |

---

## 5) Data filtering logic

The system applies multiple intelligent filters to reduce noise and show only relevant information:

### Meeting Filters (Airtable)
```
1. Source Material = "Fireflies Call" (singular, not plural)
   AND
2. (Host Name contains "deuce@recess.is" OR Participants contains "deuce@recess.is")
   AND
3. Created date = today (timezone-aware)
```

### Action Item Filters (Claude AI extraction)
```
1. Extract all action items from transcripts
   THEN
2. Filter to items where assignee matches:
   - "Deuce Thevenow" (exact match)
   - "Deuce" (first name)
   - "deuce@recess.is" (email)
   - "Unassigned" (no assignee specified)
```

### Asana Task Filters
```
1. Query by assignee (not by project) for 5 specific team members
   AND
2. For overdue tasks:
   - completed_at IS NULL (truly incomplete)
   - created_at within last 45 days (filter legacy)
   - due_on < today
```

**Result**: 5,756 tasks → 49 actionable overdue tasks (85% noise reduction)

---

## 6) Key performance optimizations

### Before & After Metrics

| Optimization | Before | After | Improvement |
|--------------|--------|-------|-------------|
| **Asana Query Strategy** | Query 100+ projects | Query 5 assignees | 20x faster |
| **Completed Task Filter** | 338 overdue shown | 49 truly overdue | 85% accuracy |
| **Legacy Data Filter** | 5,756 tasks (from 2015) | 49 recent tasks | 99% noise reduction |
| **Token Management** | Exceeded limit | Top 50 analysis | Stays under 200K |
| **Total Runtime** | 5+ minutes | ~2 minutes | 60% faster |

### Optimization Techniques Used

1. **Assignee-based queries** - Instead of querying all projects and filtering, query directly by person
2. **Double-check completion status** - Use `completed_at is null` instead of just `completed: False`
3. **Age-based filtering** - Only analyze tasks created in last 45 days
4. **Smart sampling** - For large datasets, analyze top N most critical items
5. **Parallel API calls** - No dependencies between Airtable/Asana, so fetch in parallel

---

## 7) Full code structure

### Directory Layout
```
daily-brief-agent/
├── .env                          # Secrets and configuration (gitignored)
├── .env.example                  # Template for .env
├── config.py                     # Configuration loader
├── coordinator.py                # Main orchestrator
├── scheduler.py                  # APScheduler for 4pm MT runs
├── run_for_date.py              # Test specific dates
├── test_connections.py          # Validate API credentials
├── analyze_overdue.py           # Analyze task counts
├── utils.py                     # Logging utilities
├── agents/
│   ├── __init__.py
│   ├── meeting_analyzer_agent.py    # Claude: extract action items
│   └── asana_summary_agent.py       # Claude: task insights
├── integrations/
│   ├── __init__.py
│   ├── airtable_client.py       # Fetch Fireflies transcripts
│   ├── asana_client.py          # Fetch team tasks
│   └── slack_client.py          # Post to Slack
├── logs/                         # Daily log files (gitignored)
├── README.md                     # Setup and usage guide
├── IMPLEMENTATION_NOTES.md       # Technical lessons learned
├── TROUBLESHOOTING.md            # Common issues and fixes
└── NOTION_DOCS.md                # This file
```

### Key Code Sections

**Flexible Name Matching** (`coordinator.py:63-86`)
```python
# Extract first name for flexible matching
your_first_name = Config.YOUR_NAME.split()[0].lower()  # "deuce"
your_email_prefix = "deuce@recess.is".lower()

filtered_items = []
for item in action_items:
    assignee = item.get('assignee', 'Unassigned').lower()

    # Match if: exact match, contains first name, contains email, or unassigned
    if (
        assignee == Config.YOUR_NAME.lower() or
        your_first_name in assignee or
        your_email_prefix in assignee or
        assignee == 'unassigned'
    ):
        filtered_items.append(item)
```

**Assignee-Based Queries** (`integrations/asana_client.py:244-260`)
```python
# For each team member, get their incomplete tasks
for name, user_gid in team_user_gids.items():
    logger.info(f"Fetching tasks for {name}...")

    # Query incomplete tasks assigned to this person (not by project!)
    tasks = self.tasks_api.get_tasks(
        opts={
            'assignee': user_gid,  # KEY: Query by person, not project
            'workspace': self.workspace_gid,
            'completed': False,
            'opt_fields': 'name,completed,completed_at,due_on,created_at,projects,projects.name,notes'
        }
    )
```

**Double-Check Completion** (`integrations/asana_client.py:283-285`)
```python
# Double-check that task is actually incomplete
# Use completed_at field (more reliable than completed boolean)
if task.get('completed_at') is not None:
    continue  # Skip completed tasks
```

**Age-Based Filtering** (`integrations/asana_client.py:239-242`, `294-306`)
```python
# Calculate cutoff date if age limit is configured
age_limit_cutoff = None
if Config.ASANA_TASK_AGE_LIMIT_DAYS > 0:
    age_limit_cutoff = today - timedelta(days=Config.ASANA_TASK_AGE_LIMIT_DAYS)

# Later, when processing tasks:
if age_limit_cutoff and task.get('created_at'):
    created_at = datetime.fromisoformat(task['created_at'].replace('Z', '+00:00'))
    created_date = created_at.date()

    if created_date >= age_limit_cutoff:
        overdue_tasks.append(task_data)  # Only include recent tasks
```

---

## 8) QA checklist

- [x] All API credentials configured in `.env`
- [x] Test connections pass (`python test_connections.py`)
- [x] Manual run successful (`python coordinator.py`)
- [x] Airtable field names match exactly ("Text", "Source Material", "Created", etc.)
- [x] Airtable filter uses "Fireflies Call" (singular, not "calls")
- [x] Action items filter to your name correctly
- [x] Asana queries by assignee (not by project)
- [x] Completed tasks excluded via `completed_at is null` check
- [x] Legacy tasks filtered (only last 45 days shown)
- [x] Overdue task count reasonable (~50, not 5,000+)
- [x] Slack message posts to correct channel
- [x] Scheduler runs at 4pm MT (`python scheduler.py`)
- [x] Friday weekly summary triggers correctly
- [x] Logs directory created and writable
- [x] All documentation complete
- [ ] Monitoring/alerts configured (optional)
- [ ] Backup `.env` to secure location (optional)

---

## 9) Troubleshooting

### No meetings found today

**Symptoms**: Daily brief shows 0 meetings despite having Fireflies calls

**Checklist**:
1. ✅ Check Airtable has meetings with today's date in `Created` field
2. ✅ Verify `Source Material` = "Fireflies Call" (singular, not "calls")
3. ✅ Confirm `deuce@recess.is` appears in `Host Name` OR `Participants`
4. ✅ Check `Text` field contains transcript (not empty)

**Test**:
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

---

### Action items not showing for me

**Symptoms**: Daily brief shows action items for others, but yours are missing

**Checklist**:
1. ✅ Check `YOUR_NAME` in `.env` matches transcript (try first name only: `YOUR_NAME=Deuce`)
2. ✅ Verify action items aren't assigned to someone else (working as intended)

**Test**:
```bash
python run_for_date.py 2025-10-23
# Look in logs for "assignee" values
```

---

### Completed tasks showing as overdue

**Symptoms**: Tasks marked complete in Asana appear in overdue list

**Solution**: This was fixed in latest version. Verify `asana_client.py` line 283:
```python
if task.get('completed_at') is not None:
    continue  # Skip completed tasks
```

**Verify**:
```bash
python analyze_overdue.py
# Count should be ~49, not 5,756
```

---

### Too many overdue tasks (5,000+)

**Symptoms**: Overdue list has thousands of tasks, many years old

**Solution**: Adjust age filter in `.env`:
```bash
ASANA_TASK_AGE_LIMIT_DAYS=45  # Only last 45 days
```

**Effect**:
- Before: 5,756 total (includes tasks from 2015)
- After: 49 recent (last 45 days only)

---

### Scheduler not sending at 4pm

**Checklist**:
1. ✅ Check timezone: `TIMEZONE=America/Denver` in `.env`
2. ✅ Verify time: `DAILY_BRIEF_TIME=16:00`
3. ✅ Confirm scheduler running: `ps aux | grep scheduler.py`
4. ✅ Check logs for errors: `tail -f logs/daily_brief_*.log`

---

### SSL Certificate Error (Slack)

**Symptoms**: `[SSL: CERTIFICATE_VERIFY_FAILED]`

**Solution**: Already fixed in `slack_client.py`:
```python
import ssl, certifi
ssl_context = ssl.create_default_context(cafile=certifi.where())
client = WebClient(token=Config.SLACK_BOT_TOKEN, ssl=ssl_context)
```

**If still occurring**:
```bash
pip install --upgrade certifi
```

---

## 10) References

### Quick Commands

**Start scheduler**:
```bash
cd /Users/deucethevenowworkm1/daily-brief-agent
source venv/bin/activate
python scheduler.py
```

**Test specific date**:
```bash
python run_for_date.py 2025-10-23
```

**View logs**:
```bash
tail -f logs/daily_brief_*.log
```

**Analyze overdue tasks**:
```bash
python analyze_overdue.py
```

**Stop scheduler**:
- Ctrl+C (if running in foreground)
- `pkill -f scheduler.py` (if running in background)

### API Documentation
- **Claude AI**: https://docs.anthropic.com/
- **Airtable API**: https://airtable.com/developers/web/api/introduction
- **Asana API**: https://developers.asana.com/docs
- **Slack API**: https://api.slack.com/

### Project Files
- **Setup Guide**: `README.md`
- **Technical Details**: `IMPLEMENTATION_NOTES.md`
- **Problem Solving**: `TROUBLESHOOTING.md`
- **Configuration Template**: `.env.example`

---

**Last Updated**: October 27, 2025
**Status**: Production - Running Smoothly ✅
**Your First Claude Code Workflow!** 🎉
