# Daily Brief Agent — How It Works

A reference guide for the team on how the @mention monitoring and Asana task creation system is built.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      coordinator.py                          │
│            (Orchestrates the entire daily run)               │
└────────────┬────────────────────────┬───────────────────────┘
             │                        │
    ┌────────▼────────┐     ┌────────▼────────────┐
    │  asana_client.py │     │ mention_response_   │
    │  (API calls)     │     │ agent.py (AI drafts)│
    └────────┬─────────┘     └────────────────────┘
             │
    ┌────────▼────────┐
    │   Asana API      │
    │  (Tasks, Stories,│
    │   Users)         │
    └──────────────────┘
```

---

## The @Mention Monitoring Flow

### Step 1: Find recently modified tasks

- Looks back **7 days** (configurable via `MENTION_LOOKBACK_HOURS`)
- Queries tasks assigned to each team member in `TEAM_MEMBERS`
- Gets all tasks modified in that window

### Step 2: Scan comments for @mentions

- For each modified task, fetches all comments (Asana calls them "stories")
- Parses HTML to extract `@mention` tags (Asana stores them as `<a data-asana-type="user">`)
- Checks if any `MONITORED_USERS` were mentioned

### Step 3: Determine if mention is "unanswered"

A mention is unanswered if:
1. Someone else mentioned a monitored user (not a self-mention)
2. The monitored user has **not commented** on that task after the mention timestamp

### Step 4: Filter out already-processed mentions

- Each mention has a unique `mention_story_gid`
- `data/processed_mentions.json` stores all previously processed GIDs
- Only **new** mentions (not in the tracker) get tasks created

### Step 5: Create Asana task with subtasks

- **One parent task per user per day** (e.g., "📬 Respond to Unanswered @Mentions - Jan 23")
- Parent description = count + instructions only
- **One subtask per mention** with:
  - Task name, project, link to original task
  - The comment that mentioned you
  - AI-drafted response with confidence level (✅ high / 🟡 medium / 🔴 low)
- Duplicate prevention: skips if a mention task already exists for that user today

### Step 6: Mark mentions as processed

- After task creation, GIDs are saved to `processed_mentions.json`
- Prevents duplicate tasks on the next run

---

## Key Design Decisions (Lessons Learned)

| Decision | Why | Mistake to Avoid |
|----------|-----|------------------|
| **Subtasks per mention** | Users can check off each one as they respond | Don't dump everything in one description — it's not actionable |
| **Separate tasks per user** | Each person gets their own task assigned to them | Don't combine all users' mentions into one task |
| **Persistent tracker file** | Prevents duplicate tasks across runs | Don't rely on the lookback window alone for deduplication |
| **Duplicate check before creation** | Handles agent restarts/reruns gracefully | Don't assume the agent only runs once per day |
| **Lookback > run frequency** | 7-day lookback with daily runs means nothing slips through gaps | Don't set lookback = run interval (misses mentions if a run fails) |
| **AI drafts with confidence** | Helps prioritize which responses need thought vs. quick replies | Don't skip confidence — low-confidence drafts need human judgment |

---

## File Structure That Matters

```
├── coordinator.py              # Main orchestrator - runs the daily flow
├── config.py                   # All env vars and settings
├── integrations/
│   └── asana_client.py         # All Asana API logic (tasks, mentions, subtasks)
├── agents/
│   └── mention_response_agent.py  # Claude AI drafts responses
├── utils/
│   └── mention_tracker.py      # filter_new_mentions() + mark_mentions_as_processed()
├── data/
│   └── processed_mentions.json # Persistent dedup tracker
└── .env                        # API keys + config
```

---

## Minimal .env for Mention Monitoring

```bash
ASANA_ACCESS_TOKEN=your_token
ASANA_WORKSPACE_GID=your_workspace_gid
MONITORED_USERS=Person One,Person Two    # Who to watch for @mentions
TEAM_MEMBERS=Person One,Person Two       # Whose tasks to scan
YOUR_NAME=Person One                     # Default task assignee
MENTION_LOOKBACK_HOURS=168               # 7 days
ANTHROPIC_API_KEY=your_key               # For AI draft responses
```

---

## Building a Basic Version (No Slack, No AI Drafts)

If you just want the Asana task creation without Slack or AI:

1. **Keep:** `asana_client.py` (task creation + mention detection)
2. **Keep:** `utils/mention_tracker.py` (deduplication)
3. **Skip:** `mention_response_agent.py` (just leave `suggested_response` empty)
4. **Skip:** Slack integration entirely
5. **Simplify coordinator:** Just call `get_unanswered_mentions()` → `filter_new_mentions()` → `create_respond_to_mentions_task()` → `mark_mentions_as_processed()`

The core loop is ~20 lines of code once the Asana client is set up.

---

## How the Asana API Pieces Fit Together

### Creating subtasks

Subtasks in Asana are just regular tasks with a `parent` field:

```python
subtask_data = {
    'name': 'Reply to Jack on "Budget Review"',
    'notes': 'Full details here...',
    'parent': parent_task_gid,  # This makes it a subtask
    'assignee': user_gid,
}
client.tasks_api.create_task({'data': subtask_data})
```

### Detecting @mentions in comments

Asana encodes mentions in HTML like this:

```html
<a data-asana-type="user" data-asana-gid="12345">@PersonName</a>
```

We parse with BeautifulSoup:

```python
soup = BeautifulSoup(html_text, 'html.parser')
mentions = soup.find_all('a', attrs={'data-asana-type': 'user'})
```

### Checking if a mention is unanswered

```python
# For each comment on a task:
#   - If it's FROM the monitored user → record their last reply time
#   - If it MENTIONS the monitored user → record the mention time
#
# A mention is unanswered if:
#   user_last_reply_time is None OR user_last_reply_time < mention_time
```

---

## Common Pitfalls

1. **Asana rate limits** — The API has a limit of ~150 requests/minute. If you're scanning many tasks, add delays or batch requests.

2. **Story GIDs vs Task GIDs** — Comments have their own GIDs (story GIDs). Don't confuse them with task GIDs when tracking processed mentions.

3. **Timezone handling** — Always use timezone-aware datetimes. Asana returns UTC; convert to your local timezone for display.

4. **Self-mentions** — People sometimes @mention themselves in comments. Filter these out or you'll create tasks telling someone to respond to themselves.

5. **HTML vs plain text** — Asana comments have both `text` (plain) and `html_text` (with mention markup). Use `html_text` for detecting mentions, `text` for displaying the comment content.
