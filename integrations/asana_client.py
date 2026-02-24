"""Asana client for managing tasks and fetching team progress."""
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import asana
from asana.rest import ApiException
from bs4 import BeautifulSoup
from config import Config
from utils import setup_logger
import urllib3

logger = setup_logger(__name__)

# Request timeouts in seconds
REQUEST_TIMEOUT = urllib3.Timeout(connect=10.0, read=60.0)


class AsanaClient:
    """Client for interacting with Asana API."""

    def __init__(self):
        """Initialize the Asana client with timeout configuration."""
        configuration = asana.Configuration()
        configuration.access_token = Config.ASANA_ACCESS_TOKEN

        # Configure connection pool with timeout
        pool_manager = urllib3.PoolManager(
            timeout=REQUEST_TIMEOUT,
            retries=urllib3.Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[500, 502, 503, 504]
            )
        )

        self.api_client = asana.ApiClient(configuration)
        # Override the pool manager with our timeout-configured one
        self.api_client.rest_client.pool_manager = pool_manager

        self.tasks_api = asana.TasksApi(self.api_client)
        self.projects_api = asana.ProjectsApi(self.api_client)
        self.users_api = asana.UsersApi(self.api_client)
        self.stories_api = asana.StoriesApi(self.api_client)
        self.workspace_gid = Config.ASANA_WORKSPACE_GID
        self._user_gid_cache = {}  # Cache for user name -> GID mapping
        self._token_owner_gid = None  # Cache for the API token owner's GID
        logger.info("AsanaClient initialized with timeout configuration")

    def create_task(self, title: str, notes: str, assignee_email: Optional[str] = None,
                   project_gid: Optional[str] = None, due_date: Optional[str] = None) -> Dict[str, Any]:
        """Create a new task in Asana.

        Args:
            title: Task title
            notes: Task description/notes
            assignee_email: Email of person to assign to (optional)
            project_gid: Project ID to add task to (optional)
            due_date: Due date in YYYY-MM-DD format (optional)

        Returns:
            Created task data
        """
        try:
            task_data = {
                'name': title,
                'notes': notes,
                'workspace': self.workspace_gid,
            }

            if due_date:
                task_data['due_on'] = due_date

            if project_gid:
                task_data['projects'] = [project_gid]

            # Assign to user if email provided
            if assignee_email:
                try:
                    users = self.users_api.get_users_for_workspace(self.workspace_gid, opts={})
                    user = next((u for u in users if u.get('email') == assignee_email), None)
                    if user:
                        task_data['assignee'] = user['gid']
                except Exception as e:
                    logger.warning(f"Could not assign task to {assignee_email}: {e}")

            # Create the task
            result = self.tasks_api.create_task({'data': task_data})

            logger.info(f"Created task: {title} (ID: {result['gid']})")
            return result

        except ApiException as e:
            logger.error(f"Error creating task '{title}': {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating task '{title}': {e}")
            raise

    def find_existing_mention_task_for_today(self, assignee_name: str) -> Optional[Dict[str, Any]]:
        """Check if a 'Respond to @Mentions' task already exists for today for this user.

        Args:
            assignee_name: Name of the user to check for

        Returns:
            Existing task data if found, None otherwise
        """
        today = datetime.now(Config.TIMEZONE)
        date_pattern = today.strftime('%b %d')  # e.g., "Jan 20"

        try:
            # Get the user's GID
            user_gid = self.get_user_gid_by_name(assignee_name)
            if not user_gid:
                logger.warning(f"Could not find user GID for {assignee_name}")
                return None

            # Search for incomplete tasks assigned to this user with today's date in title
            tasks = self.tasks_api.get_tasks(
                opts={
                    'assignee': user_gid,
                    'workspace': self.workspace_gid,
                    'completed': False,
                    'opt_fields': 'name,gid,created_at'
                }
            )

            # Look for a matching mention task
            for task in tasks:
                task_name = task.get('name', '')
                # Match tasks like "📬 Respond to Unanswered @Mentions - Jan 20"
                if '📬' in task_name and 'Mentions' in task_name and date_pattern in task_name:
                    logger.info(f"Found existing mention task for {assignee_name}: {task['gid']} - {task_name}")
                    return task

            return None

        except Exception as e:
            logger.warning(f"Error checking for existing mention task: {e}")
            return None

    def create_respond_to_mentions_task(self, mentions: List[Dict[str, Any]],
                                        assignee_name: str = None) -> Optional[Dict[str, Any]]:
        """Create a daily task to respond to unanswered @mentions, with subtasks for each mention.

        Creates a parent task with a summary (total count + instructions) and individual
        subtasks for each mention containing the full details. Users can mark each subtask
        complete as they respond.

        Args:
            mentions: List of unanswered mention dictionaries with draft responses
            assignee_name: Name of person to assign task to (from MONITORED_USERS)

        Returns:
            Created task data, or None if no mentions to process
        """
        if not mentions:
            logger.info("No new mentions to create task for")
            return None

        today = datetime.now(Config.TIMEZONE)
        date_str = today.strftime('%B %d, %Y')

        # Build the main task description (summary only)
        notes_parts = [
            f"📬 Unanswered @Mentions - {date_str}",
            "=" * 50,
            f"You have {len(mentions)} mention(s) that need responses.",
            "",
            "Instructions:",
            "1. Review each mention below",
            "2. Click the task link to go to Asana",
            "3. Post your response (draft provided)",
            "4. Check off the subtask when done",
            "",
            "=" * 50,
            "This task was auto-generated by Daily Brief Agent.",
            f"Generated: {today.strftime('%I:%M %p %Z')}",
        ]

        task_notes = '\n'.join(notes_parts)

        # Determine assignee
        if assignee_name:
            assignee = assignee_name
        else:
            assignee = Config.YOUR_NAME

        # Get assignee GID
        assignee_gid = None
        try:
            assignee_gid = self.get_user_gid_by_name(assignee)
        except Exception as e:
            logger.warning(f"Could not find assignee {assignee}: {e}")

        try:
            task_data = {
                'name': f"📬 Respond to Unanswered @Mentions - {today.strftime('%b %d')}",
                'notes': task_notes,
                'workspace': self.workspace_gid,
                'due_on': today.strftime('%Y-%m-%d'),
            }

            if assignee_gid:
                task_data['assignee'] = assignee_gid

            # Create the main task
            result = self.tasks_api.create_task({'data': task_data}, opts={})
            parent_task_gid = result['gid']

            logger.info(f"Created respond-to-mentions task: {parent_task_gid} with {len(mentions)} mentions")

            # Check if this task is for someone other than the token owner (GID-based, not name-based)
            token_owner_gid = self._get_token_owner_gid()
            is_other_user = (
                assignee_gid is not None
                and token_owner_gid is not None
                and assignee_gid != token_owner_gid
            )

            # Remove token owner as follower if task is for another user
            if is_other_user:
                self._remove_token_owner_as_follower(parent_task_gid)

            # Create a subtask for each individual mention
            for i, mention in enumerate(mentions, 1):
                try:
                    self._create_mention_subtask(parent_task_gid, mention, i, assignee_gid, is_other_user)
                except Exception as e:
                    logger.error(f"Failed to create subtask #{i} for mention: {e}")

            return result

        except ApiException as e:
            logger.error(f"Error creating respond-to-mentions task: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating respond-to-mentions task: {e}")
            raise

    def _create_mention_subtask(self, parent_task_gid: str, mention: Dict[str, Any],
                                 index: int, assignee_gid: Optional[str] = None,
                                 remove_owner_follower: bool = False) -> Optional[Dict[str, Any]]:
        """Create a subtask for a single unanswered mention.

        Args:
            parent_task_gid: GID of the parent mentions task
            mention: Mention dictionary with details and draft response
            index: The mention number (for ordering)
            assignee_gid: GID of the user to assign to
            remove_owner_follower: If True, remove the API token owner as follower

        Returns:
            Created subtask data, or None on failure
        """
        hours_ago = mention.get('hours_since_mention', 0)
        if hours_ago < 1:
            time_str = "just now"
        elif hours_ago < 24:
            time_str = f"{int(hours_ago)} hours ago"
        else:
            time_str = f"{int(hours_ago / 24)} days ago"

        confidence = mention.get('response_confidence', 'unknown')
        confidence_indicator = {'high': '✅', 'medium': '🟡', 'low': '🔴'}.get(confidence, '⚪')

        author_name = mention.get('author_name', 'Unknown')
        task_name = mention.get('task_name', 'Unknown Task')

        # Subtask name: concise but informative
        subtask_name = f"Reply to {author_name} on \"{task_name}\""

        # Subtask description: all the details for this specific mention
        subtask_notes_parts = [
            f"📋 Task: {task_name}",
            f"📁 Project: {mention.get('project_name', 'No Project')}",
            f"🔗 Link: {mention.get('task_url', 'No link')}",
            f"👤 From: {author_name} ({time_str})",
            "",
            "💬 Comment:",
            f"   \"{mention.get('comment_text', 'No comment')}\"",
            "",
            f"{confidence_indicator} Draft Response ({confidence} confidence):",
            f"   \"{mention.get('suggested_response', 'No draft available')}\"",
        ]

        subtask_notes = '\n'.join(subtask_notes_parts)

        subtask_data = {
            'name': subtask_name,
            'notes': subtask_notes,
            'parent': parent_task_gid,
        }

        if assignee_gid:
            subtask_data['assignee'] = assignee_gid

        result = self.tasks_api.create_task({'data': subtask_data}, opts={})
        logger.info(f"Created mention subtask #{index}: {result['gid']} - {subtask_name}")

        if remove_owner_follower:
            self._remove_token_owner_as_follower(result['gid'])

        return result

    def get_completed_tasks_today(self) -> List[Dict[str, Any]]:
        """Get all tasks completed today for tracked team members.

        Returns:
            List of completed tasks with assignee information
        """
        if not Config.TEAM_MEMBERS:
            logger.warning("No TEAM_MEMBERS configured - skipping task fetch")
            return []

        today = datetime.now(Config.TIMEZONE).date()
        today_start = datetime.combine(today, datetime.min.time()).astimezone(Config.TIMEZONE)

        logger.info(f"Fetching tasks completed today ({today}) for {len(Config.TEAM_MEMBERS)} team members")

        try:
            completed_tasks = []

            # Get users in workspace
            users = self.users_api.get_users_for_workspace(self.workspace_gid, opts={})

            # Map team member names to user GIDs
            team_user_gids = {}
            for user in users:
                user_name = user.get('name', '')
                if user_name in Config.TEAM_MEMBERS:
                    team_user_gids[user_name] = user['gid']

            logger.info(f"Found {len(team_user_gids)} team members in Asana: {list(team_user_gids.keys())}")

            # For each team member, get their completed tasks
            for name, user_gid in team_user_gids.items():
                try:
                    # Query tasks assigned to this person, completed today
                    tasks = self.tasks_api.get_tasks(
                        opts={
                            'assignee': user_gid,
                            'workspace': self.workspace_gid,
                            'completed_since': today_start.isoformat(),
                            'opt_fields': 'name,completed,completed_at,projects,projects.name,notes,due_on'
                        }
                    )

                    for task in tasks:
                        if task.get('completed') and task.get('completed_at'):
                            completed_at = datetime.fromisoformat(task['completed_at'].replace('Z', '+00:00'))
                            completed_at = completed_at.astimezone(Config.TIMEZONE)

                            if completed_at >= today_start:
                                project_name = 'No Project'
                                if task.get('projects') and len(task['projects']) > 0:
                                    project_name = task['projects'][0].get('name', 'No Project')

                                completed_tasks.append({
                                    'gid': task['gid'],
                                    'name': task['name'],
                                    'completed_at': completed_at.isoformat(),
                                    'assignee': name,
                                    'assignee_gid': user_gid,
                                    'project': project_name,
                                    'notes': task.get('notes', ''),
                                })
                except Exception as e:
                    logger.warning(f"Could not fetch tasks for {name}: {e}")
                    continue

            logger.info(f"Found {len(completed_tasks)} tasks completed today")
            return completed_tasks

        except ApiException as e:
            logger.error(f"Error fetching completed tasks: {e}")
            raise
        except Exception as e:
            logger.error(f"Error fetching completed tasks: {e}")
            raise

    def get_completed_tasks_this_week(self) -> List[Dict[str, Any]]:
        """Get all tasks completed this week (Monday to today) for tracked team members.

        Returns:
            List of completed tasks from this week
        """
        if not Config.TEAM_MEMBERS:
            logger.warning("No TEAM_MEMBERS configured - skipping task fetch")
            return []

        today = datetime.now(Config.TIMEZONE).date()
        days_since_monday = today.weekday()
        monday = today - timedelta(days=days_since_monday)
        week_start = datetime.combine(monday, datetime.min.time()).astimezone(Config.TIMEZONE)

        logger.info(f"Fetching tasks completed this week (since {monday}) for {len(Config.TEAM_MEMBERS)} team members")

        try:
            completed_tasks = []

            # Get users in workspace
            users = self.users_api.get_users_for_workspace(self.workspace_gid, opts={})

            # Map team member names to user GIDs
            team_user_gids = {}
            for user in users:
                user_name = user.get('name', '')
                if user_name in Config.TEAM_MEMBERS:
                    team_user_gids[user_name] = user['gid']

            logger.info(f"Found {len(team_user_gids)} team members in Asana: {list(team_user_gids.keys())}")

            # For each team member, get their completed tasks this week
            for name, user_gid in team_user_gids.items():
                try:
                    # Query tasks assigned to this person, completed this week
                    tasks = self.tasks_api.get_tasks(
                        opts={
                            'assignee': user_gid,
                            'workspace': self.workspace_gid,
                            'completed_since': week_start.isoformat(),
                            'opt_fields': 'name,completed,completed_at,projects,projects.name,notes,due_on'
                        }
                    )

                    for task in tasks:
                        if task.get('completed') and task.get('completed_at'):
                            completed_at = datetime.fromisoformat(task['completed_at'].replace('Z', '+00:00'))
                            completed_at = completed_at.astimezone(Config.TIMEZONE)

                            if completed_at >= week_start:
                                project_name = 'No Project'
                                if task.get('projects') and len(task['projects']) > 0:
                                    project_name = task['projects'][0].get('name', 'No Project')

                                completed_tasks.append({
                                    'gid': task['gid'],
                                    'name': task['name'],
                                    'completed_at': completed_at.isoformat(),
                                    'assignee': name,
                                    'assignee_gid': user_gid,
                                    'project': project_name,
                                    'notes': task.get('notes', ''),
                                })
                except Exception as e:
                    logger.warning(f"Could not fetch tasks for {name}: {e}")
                    continue

            logger.info(f"Found {len(completed_tasks)} tasks completed this week")
            return completed_tasks

        except ApiException as e:
            logger.error(f"Error fetching week's completed tasks: {e}")
            raise
        except Exception as e:
            logger.error(f"Error fetching week's completed tasks: {e}")
            raise

    def get_overdue_tasks(self) -> List[Dict[str, Any]]:
        """Get all overdue tasks for tracked team members.

        Returns:
            List of overdue tasks with assignee information (filtered by age if configured)
        """
        if not Config.TEAM_MEMBERS:
            logger.warning("No TEAM_MEMBERS configured - skipping task fetch")
            return []

        today = datetime.now(Config.TIMEZONE).date()
        logger.info(f"Fetching overdue tasks (due before {today}) for {len(Config.TEAM_MEMBERS)} team members")

        # Calculate cutoff date if age limit is configured
        age_limit_cutoff = None
        if Config.ASANA_TASK_AGE_LIMIT_DAYS > 0:
            age_limit_cutoff = today - timedelta(days=Config.ASANA_TASK_AGE_LIMIT_DAYS)
            logger.info(f"Filtering to tasks created after {age_limit_cutoff} (last {Config.ASANA_TASK_AGE_LIMIT_DAYS} days)")

        try:
            overdue_tasks = []
            overdue_tasks_before_filter = []

            # Get users in workspace
            users = self.users_api.get_users_for_workspace(self.workspace_gid, opts={})

            # Map team member names to user GIDs
            team_user_gids = {}
            for user in users:
                user_name = user.get('name', '')
                if user_name in Config.TEAM_MEMBERS:
                    team_user_gids[user_name] = user['gid']

            logger.info(f"Found {len(team_user_gids)} team members in Asana: {list(team_user_gids.keys())}")

            # For each team member, get their incomplete tasks
            for name, user_gid in team_user_gids.items():
                try:
                    # Query incomplete tasks assigned to this person
                    # Include created_at to filter by age
                    tasks = self.tasks_api.get_tasks(
                        opts={
                            'assignee': user_gid,
                            'workspace': self.workspace_gid,
                            'completed': False,
                            'opt_fields': 'name,completed,completed_at,due_on,created_at,projects,projects.name,notes'
                        }
                    )

                    for task in tasks:
                        # Double-check that task is actually incomplete
                        # Use completed_at field (more reliable than completed boolean)
                        # Incomplete tasks have completed_at = None
                        if task.get('completed_at') is not None:
                            continue  # Skip completed tasks (have a completion timestamp)

                        if task.get('due_on'):
                            due_date = datetime.strptime(task['due_on'], '%Y-%m-%d').date()

                            if due_date < today:
                                days_overdue = (today - due_date).days
                                project_name = 'No Project'
                                if task.get('projects') and len(task['projects']) > 0:
                                    project_name = task['projects'][0].get('name', 'No Project')

                                task_data = {
                                    'gid': task['gid'],
                                    'name': task['name'],
                                    'due_on': task['due_on'],
                                    'days_overdue': days_overdue,
                                    'assignee': name,
                                    'assignee_gid': user_gid,
                                    'project': project_name,
                                    'notes': task.get('notes', ''),
                                }

                                # Track all overdue tasks for logging
                                overdue_tasks_before_filter.append(task_data)

                                # Apply age filter if configured
                                if age_limit_cutoff and task.get('created_at'):
                                    created_at = datetime.fromisoformat(task['created_at'].replace('Z', '+00:00'))
                                    created_date = created_at.date()

                                    # Only include if created after cutoff
                                    if created_date >= age_limit_cutoff:
                                        overdue_tasks.append(task_data)
                                else:
                                    # No filter or no created_at field, include task
                                    overdue_tasks.append(task_data)

                except Exception as e:
                    logger.warning(f"Could not fetch tasks for {name}: {e}")
                    continue

            # Log filtering results
            total_overdue = len(overdue_tasks_before_filter)
            filtered_overdue = len(overdue_tasks)
            filtered_out = total_overdue - filtered_overdue

            if age_limit_cutoff:
                logger.info(f"Found {total_overdue} total overdue tasks, {filtered_overdue} within last {Config.ASANA_TASK_AGE_LIMIT_DAYS} days ({filtered_out} filtered out)")
            else:
                logger.info(f"Found {filtered_overdue} overdue tasks")

            return overdue_tasks

        except ApiException as e:
            logger.error(f"Error fetching overdue tasks: {e}")
            raise
        except Exception as e:
            logger.error(f"Error fetching overdue tasks: {e}")
            raise

    # ============================================================
    # Methods for @Mention Monitoring
    # ============================================================

    def get_user_gid_by_name(self, user_name: str) -> Optional[str]:
        """Get user GID from name, with caching.

        Args:
            user_name: The display name of the user in Asana

        Returns:
            User GID string or None if not found
        """
        if user_name in self._user_gid_cache:
            return self._user_gid_cache[user_name]

        try:
            users = self.users_api.get_users_for_workspace(self.workspace_gid, opts={})
            for user in users:
                name = user.get('name', '')
                gid = user.get('gid')
                self._user_gid_cache[name] = gid
                if name == user_name:
                    return gid
        except Exception as e:
            logger.warning(f"Error fetching users: {e}")

        return None

    def _get_token_owner_gid(self) -> Optional[str]:
        """Get the GID of the user who owns the API access token.

        Uses the Asana 'me' endpoint to identify the authenticated user.
        Result is cached after first call.

        Returns:
            User GID string or None if lookup fails
        """
        if self._token_owner_gid is not None:
            return self._token_owner_gid

        try:
            me = self.users_api.get_user('me', opts={})
            self._token_owner_gid = me.get('gid')
            logger.info(f"Token owner identified: {me.get('name')} ({self._token_owner_gid})")
            return self._token_owner_gid
        except Exception as e:
            logger.warning(f"Could not identify token owner: {e}")
            return None

    def _remove_token_owner_as_follower(self, task_gid: str) -> None:
        """Remove the API token owner as a follower from a task.

        The Asana API automatically adds the token owner as a follower
        on every task created through the API. This method removes that
        auto-added follower so the token owner doesn't get inbox notifications
        for tasks meant for other users.

        Args:
            task_gid: The GID of the task to remove the follower from
        """
        owner_gid = self._get_token_owner_gid()
        if not owner_gid:
            logger.warning("Cannot remove token owner as follower - GID unknown")
            return

        try:
            self.tasks_api.remove_follower_for_task(
                body={'data': {'followers': [owner_gid]}},
                task_gid=task_gid,
                opts={}
            )
            logger.info(f"Removed token owner as follower from task {task_gid}")
        except Exception as e:
            logger.warning(f"Failed to remove token owner as follower from task {task_gid}: {e}")

    def get_tasks_modified_since(self, since: datetime) -> List[Dict[str, Any]]:
        """Get tasks that have been modified since a given time.

        Args:
            since: Datetime to look back from

        Returns:
            List of task dictionaries with basic info
        """
        modified_since = since.isoformat()
        tasks = []

        try:
            # Get users in workspace to iterate through
            users = self.users_api.get_users_for_workspace(self.workspace_gid, opts={})

            # Map team member names to user GIDs
            team_user_gids = {}
            for user in users:
                user_name = user.get('name', '')
                if user_name in Config.TEAM_MEMBERS:
                    team_user_gids[user_name] = user['gid']

            logger.info(f"Checking tasks modified since {since} for {len(team_user_gids)} team members")

            # For each team member, get their recently modified tasks
            seen_gids = set()
            for name, user_gid in team_user_gids.items():
                try:
                    user_tasks = self.tasks_api.get_tasks(
                        opts={
                            'assignee': user_gid,
                            'workspace': self.workspace_gid,
                            'modified_since': modified_since,
                            'opt_fields': 'gid,name,notes,projects,projects.name,permalink_url,modified_at'
                        }
                    )

                    for task in user_tasks:
                        if task['gid'] not in seen_gids:
                            seen_gids.add(task['gid'])
                            project_name = 'No Project'
                            if task.get('projects') and len(task['projects']) > 0:
                                project_name = task['projects'][0].get('name', 'No Project')

                            tasks.append({
                                'gid': task['gid'],
                                'name': task.get('name', 'Untitled'),
                                'notes': task.get('notes', ''),
                                'project_name': project_name,
                                'permalink_url': task.get('permalink_url', f'https://app.asana.com/0/0/{task["gid"]}')
                            })
                except Exception as e:
                    logger.warning(f"Could not fetch modified tasks for {name}: {e}")
                    continue

            logger.info(f"Found {len(tasks)} tasks modified since {since}")
            return tasks

        except Exception as e:
            logger.error(f"Error fetching modified tasks: {e}")
            return []

    def get_stories_for_task(self, task_gid: str) -> List[Dict[str, Any]]:
        """Get all comments (stories) for a task.

        Args:
            task_gid: The task GID

        Returns:
            List of comment dictionaries
        """
        try:
            stories = self.stories_api.get_stories_for_task(
                task_gid,
                opts={
                    'opt_fields': 'gid,created_at,created_by,created_by.name,created_by.gid,resource_subtype,text,html_text'
                }
            )

            comments = []
            for story in stories:
                # Only include actual comments, not system events
                if story.get('resource_subtype') == 'comment_added':
                    created_by = story.get('created_by', {})
                    comments.append({
                        'gid': story['gid'],
                        'created_at': story.get('created_at'),
                        'author_name': created_by.get('name', 'Unknown'),
                        'author_gid': created_by.get('gid'),
                        'text': story.get('text', ''),
                        'html_text': story.get('html_text', '')
                    })

            return comments

        except Exception as e:
            logger.warning(f"Error fetching stories for task {task_gid}: {e}")
            return []

    def extract_mentions_from_html(self, html_text: str) -> List[Dict[str, str]]:
        """Parse html_text to extract @mentions.

        Asana encodes mentions as:
        <a data-asana-type="user" data-asana-gid="USER_GID">@Name</a>

        Args:
            html_text: The HTML content of the comment

        Returns:
            List of dicts with user_gid and user_name
        """
        mentions = []
        if not html_text:
            return mentions

        try:
            soup = BeautifulSoup(html_text, 'html.parser')
            mention_links = soup.find_all('a', attrs={'data-asana-type': 'user'})

            for link in mention_links:
                user_gid = link.get('data-asana-gid')
                user_name = link.get_text().lstrip('@')
                if user_gid:
                    mentions.append({
                        'user_gid': user_gid,
                        'user_name': user_name
                    })
        except Exception as e:
            logger.warning(f"Error parsing mentions from HTML: {e}")

        return mentions

    def get_unanswered_mentions(
        self,
        monitored_user_names: List[str],
        lookback_hours: int = 168
    ) -> List[Dict[str, Any]]:
        """Find comments that @mention monitored users and haven't been responded to.

        A mention is considered "unanswered" if:
        1. It mentions one of the monitored users
        2. It wasn't written by that user (not a self-mention)
        3. The monitored user hasn't commented on the task after the mention

        Args:
            monitored_user_names: List of user names to monitor
            lookback_hours: How many hours back to look

        Returns:
            List of unanswered mention dictionaries
        """
        # Get user GIDs for monitored users
        monitored_user_gids = {}
        for name in monitored_user_names:
            gid = self.get_user_gid_by_name(name)
            if gid:
                monitored_user_gids[gid] = name
            else:
                logger.warning(f"Could not find user GID for: {name}")

        if not monitored_user_gids:
            logger.warning("No monitored users found in workspace")
            return []

        logger.info(f"Monitoring mentions for: {list(monitored_user_gids.values())}")

        since = datetime.now(Config.TIMEZONE) - timedelta(hours=lookback_hours)
        unanswered = []

        # Get recently modified tasks
        tasks = self.get_tasks_modified_since(since)
        logger.info(f"Checking {len(tasks)} tasks for unanswered mentions")

        for task in tasks:
            task_gid = task['gid']
            comments = self.get_stories_for_task(task_gid)

            if not comments:
                continue

            # For each monitored user, check if they were mentioned and haven't replied
            for user_gid, user_name in monitored_user_gids.items():
                mentions_to_user = []
                user_last_reply_at = None

                for comment in comments:
                    try:
                        comment_time = datetime.fromisoformat(
                            comment['created_at'].replace('Z', '+00:00')
                        ).astimezone(Config.TIMEZONE)
                    except (ValueError, TypeError):
                        continue

                    # Check if this comment is from the monitored user
                    if comment.get('author_gid') == user_gid:
                        if user_last_reply_at is None or comment_time > user_last_reply_at:
                            user_last_reply_at = comment_time
                        continue

                    # Check if this comment mentions the monitored user
                    mentions = self.extract_mentions_from_html(comment.get('html_text', ''))
                    for mention in mentions:
                        if mention['user_gid'] == user_gid:
                            mentions_to_user.append({
                                'comment': comment,
                                'mentioned_at': comment_time
                            })

                # Check which mentions are unanswered
                for mention_data in mentions_to_user:
                    mention_time = mention_data['mentioned_at']

                    # Is this mention within our lookback window?
                    if mention_time < since:
                        continue

                    # Did the user reply after this mention?
                    has_replied = (
                        user_last_reply_at is not None and
                        user_last_reply_at > mention_time
                    )

                    if not has_replied:
                        hours_since = (datetime.now(Config.TIMEZONE) - mention_time).total_seconds() / 3600

                        unanswered.append({
                            'task_gid': task_gid,
                            'task_name': task.get('name', 'Unknown Task'),
                            'task_url': task.get('permalink_url', f'https://app.asana.com/0/0/{task_gid}'),
                            'project_name': task.get('project_name', 'No Project'),
                            'task_description': task.get('notes', ''),

                            'mention_story_gid': mention_data['comment']['gid'],
                            'mentioned_user_name': user_name,
                            'mentioned_user_gid': user_gid,

                            'author_name': mention_data['comment'].get('author_name', 'Unknown'),
                            'author_gid': mention_data['comment'].get('author_gid'),

                            'comment_text': mention_data['comment'].get('text', ''),
                            'comment_created_at': mention_time.isoformat(),
                            'hours_since_mention': round(hours_since, 1),

                            'recent_comments': comments[-5:]  # Last 5 comments for context
                        })

        logger.info(f"Found {len(unanswered)} unanswered mentions")
        return unanswered
