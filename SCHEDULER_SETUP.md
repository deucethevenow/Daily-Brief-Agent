# Daily Brief Scheduler - Using macOS launchd

## ✅ Current Setup (Reliable)

Your daily brief now runs using **macOS launchd**, Apple's native scheduler that:
- ✅ Survives computer restarts
- ✅ Handles sleep/wake automatically
- ✅ Runs even when you're not logged in
- ✅ Automatically restarts if it crashes
- ✅ More reliable than Python `schedule` library

---

## 📅 Schedule

**Runs daily at 4:00 PM Mountain Time**
- Monday-Thursday: Daily brief
- Friday: Enhanced weekly summary

---

## 🔧 Managing the Scheduler

### Check Status
```bash
launchctl list | grep com.recess.dailybrief
```

**Output explained:**
- `47102  0  com.recess.dailybrief`
  - `47102` = Last process ID (changes each run)
  - `0` = Exit code (0 = success)
  - Status shows it's loaded and running

### Start Manually (for testing)
```bash
launchctl start com.recess.dailybrief
```

### Stop the Scheduler
```bash
launchctl unload ~/Library/LaunchAgents/com.recess.dailybrief.plist
```

### Restart the Scheduler
```bash
launchctl unload ~/Library/LaunchAgents/com.recess.dailybrief.plist
launchctl load ~/Library/LaunchAgents/com.recess.dailybrief.plist
```

---

## 📊 Monitoring

### View Recent Logs
```bash
tail -50 ~/daily-brief-agent/logs/daily_brief_$(date +%Y%m%d).log
```

### View launchd Output
```bash
tail -50 ~/daily-brief-agent/logs/launchd.out.log
```

### View launchd Errors
```bash
tail -50 ~/daily-brief-agent/logs/launchd.err.log
```

### Check if Today's Brief Ran
```bash
ls -la ~/daily-brief-agent/logs/ | grep $(date +%Y%m%d)
```

---

## ⚠️ What Happened Before (Why We Switched)

### Old System: Python `schedule` Library
**Problems:**
- ❌ Stopped working if computer slept
- ❌ Stopped working if terminal closed
- ❌ Didn't survive restarts
- ❌ Required keeping a Python process running 24/7
- ❌ **Result**: Missed Nov 2 and Nov 3 briefs

**Evidence from logs:**
- Nov 1: ✅ Ran at 4:50 PM (but scheduler was already late)
- Nov 2: ❌ Missed (no log file)
- Nov 3: ❌ Missed (until we fixed it)

### New System: macOS launchd
**Benefits:**
- ✅ Integrated with macOS
- ✅ Handles all edge cases automatically
- ✅ Production-grade reliability
- ✅ Used by Apple and all major Mac apps

---

## 🔄 What Happens After Restart

The scheduler **automatically starts** when you log in. No action needed!

To verify after a restart:
```bash
launchctl list | grep com.recess.dailybrief
```

---

## 📝 Configuration File Location

**plist file:** `/Users/deucethevenowworkm1/Library/LaunchAgents/com.recess.dailybrief.plist`

This tells macOS:
- What to run: `coordinator.py` with your virtual environment Python
- When to run: Daily at 16:00 (4 PM)
- Where to log: `logs/launchd.out.log` and `logs/launchd.err.log`

---

## 🚨 Error Notifications

If anything fails, you'll receive **immediate Slack notifications** with:
- ⚠️ What went wrong
- Which component failed
- What data is missing
- Reminder to check logs

---

## 🎯 Success Metrics (Today's Test Run)

**Nov 3, 2025 at 5:06 PM:**
- ✅ Found 2 meetings from today
- ✅ Extracted 26 action items (using Sonnet 4.5)
- ✅ Found 14 completed tasks
- ✅ Found 28 overdue tasks (last 45 days)
- ✅ Generated AI insights
- ✅ Sent to Slack successfully
- ✅ **Total runtime**: 4 minutes

---

## 💡 Troubleshooting

### Brief didn't run today
1. Check if it's loaded:
   ```bash
   launchctl list | grep com.recess.dailybrief
   ```

2. Check for errors:
   ```bash
   tail -50 ~/daily-brief-agent/logs/launchd.err.log
   ```

3. Restart it:
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.recess.dailybrief.plist
   launchctl load ~/Library/LaunchAgents/com.recess.dailybrief.plist
   ```

### Want to change the time?
1. Edit the plist file:
   ```bash
   nano ~/Library/LaunchAgents/com.recess.dailybrief.plist
   ```

2. Change the Hour/Minute values:
   ```xml
   <key>StartCalendarInterval</key>
   <dict>
       <key>Hour</key>
       <integer>16</integer>  <!-- Change this (0-23) -->
       <key>Minute</key>
       <integer>0</integer>   <!-- Change this (0-59) -->
   </dict>
   ```

3. Reload:
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.recess.dailybrief.plist
   launchctl load ~/Library/LaunchAgents/com.recess.dailybrief.plist
   ```

---

## 🔍 Quick Reference

| Task | Command |
|------|---------|
| Check status | `launchctl list \| grep dailybrief` |
| Start manually | `launchctl start com.recess.dailybrief` |
| Stop scheduler | `launchctl unload ~/Library/LaunchAgents/com.recess.dailybrief.plist` |
| Start scheduler | `launchctl load ~/Library/LaunchAgents/com.recess.dailybrief.plist` |
| View today's log | `tail -50 ~/daily-brief-agent/logs/daily_brief_$(date +%Y%m%d).log` |
| View errors | `tail -50 ~/daily-brief-agent/logs/launchd.err.log` |

---

**Last Updated**: November 3, 2025
**Status**: ✅ Production - Running Reliably with launchd
