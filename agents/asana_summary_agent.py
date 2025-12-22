"""Asana Summary Agent - Analyzes Asana tasks and provides intelligent summaries."""
import json
from typing import List, Dict, Any
from anthropic import Anthropic
from config import Config
from utils import setup_logger

logger = setup_logger(__name__)


class AsanaSummaryAgent:
    """Agent that analyzes Asana task data and generates intelligent summaries."""

    def __init__(self):
        """Initialize the Asana Summary Agent."""
        self.client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self.model = "claude-sonnet-4-5-20250929"  # Claude Sonnet 4.5 (Sep 2025)
        logger.info("AsanaSummaryAgent initialized")

    def generate_daily_summary(self, completed_tasks: List[Dict[str, Any]],
                              overdue_tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a daily summary of team activity.

        Args:
            completed_tasks: List of tasks completed today
            overdue_tasks: List of overdue tasks

        Returns:
            Dictionary with formatted summary and insights
        """
        logger.info("Generating daily Asana summary")

        try:
            # Sort overdue tasks by days_overdue (most overdue first) and limit to top 50
            # This prevents token limit issues with large numbers of overdue tasks
            sorted_overdue = sorted(overdue_tasks, key=lambda x: x.get('days_overdue', 0), reverse=True)
            overdue_sample = sorted_overdue[:50]

            logger.info(f"Analyzing {len(overdue_sample)} most overdue tasks (out of {len(overdue_tasks)} total)")

            # Prepare data for Claude
            data_summary = {
                'completed_count': len(completed_tasks),
                'overdue_count': len(overdue_tasks),
                'overdue_sample_count': len(overdue_sample),
                'completed_tasks': [
                    {
                        'name': t['name'],
                        'assignee': t['assignee'],
                        'project': t['project']
                    }
                    for t in completed_tasks
                ],
                'overdue_tasks_sample': [
                    {
                        'name': t['name'],
                        'assignee': t['assignee'],
                        'project': t['project'],
                        'days_overdue': t['days_overdue']
                    }
                    for t in overdue_sample
                ]
            }

            prompt = """You are a team productivity analyst. Review the daily Asana task data and provide insights.

NOTE: You're seeing a sample of the most overdue tasks (up to 50) when the total count is large.

Analyze the completed and overdue tasks to:
1. Summarize team productivity (what was accomplished)
2. Identify any concerning patterns (e.g., specific team members with many overdue items)
3. Highlight notable accomplishments
4. Provide a brief, actionable insight or recommendation

Return a JSON object with:
{
  "overview": "Brief overview paragraph (2-3 sentences)",
  "team_highlights": ["Highlight 1", "Highlight 2", ...],
  "concerns": ["Concern 1", "Concern 2", ...],
  "recommendation": "One actionable recommendation"
}

Keep it concise and actionable. Focus on patterns, not listing every task.

IMPORTANT: Only return the JSON object, no additional text."""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[
                    {"role": "user", "content": f"{prompt}\n\nTask Data:\n{json.dumps(data_summary, indent=2)}"}
                ]
            )

            response_text = response.content[0].text.strip()

            # Parse JSON response
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            summary = json.loads(response_text)
            logger.info("Daily summary generated successfully")
            return summary

        except Exception as e:
            logger.error(f"Error generating daily summary: {e}")
            return {
                'overview': f"Today the team completed {len(completed_tasks)} tasks. There are {len(overdue_tasks)} overdue tasks.",
                'team_highlights': [],
                'concerns': [],
                'recommendation': 'Review overdue tasks and reprioritize as needed.'
            }

    def generate_weekly_summary(self, completed_tasks: List[Dict[str, Any]],
                               overdue_tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a weekly summary with high-level insights focused on tasks.

        Args:
            completed_tasks: List of tasks completed this week
            overdue_tasks: List of overdue tasks

        Returns:
            Dictionary with weekly summary, accomplishments, and team performance
        """
        logger.info("Generating weekly Asana summary")

        try:
            # Group completed tasks by team member
            tasks_by_person = {}
            for task in completed_tasks:
                assignee = task.get('assignee', 'Unassigned')
                if assignee not in tasks_by_person:
                    tasks_by_person[assignee] = []
                tasks_by_person[assignee].append(task)

            # Limit overdue tasks sample to top 30 most overdue
            sorted_overdue = sorted(overdue_tasks, key=lambda x: x.get('days_overdue', 0), reverse=True)
            overdue_sample = sorted_overdue[:30]

            logger.info(f"Analyzing {len(overdue_sample)} most overdue tasks (out of {len(overdue_tasks)} total) for weekly summary")

            # Prepare data
            data_summary = {
                'week_completed_count': len(completed_tasks),
                'overdue_count': len(overdue_tasks),
                'overdue_sample_count': len(overdue_sample),
                'completed_by_person': {
                    person: len(tasks) for person, tasks in tasks_by_person.items()
                },
                'top_performers': self._get_top_performers(completed_tasks),
                'sample_tasks': [
                    {'name': t['name'], 'assignee': t['assignee'], 'project': t.get('project', 'N/A')}
                    for t in completed_tasks[:20]  # Sample of tasks for context
                ],
                'critical_overdue_sample': [
                    {'name': t['name'], 'assignee': t['assignee'], 'days_overdue': t['days_overdue']}
                    for t in overdue_sample
                ]
            }

            prompt = """You are a team productivity analyst creating a weekly executive summary.

Review the weekly Asana task data and provide a comprehensive summary suitable for leadership.

Generate:
1. A high-level overview of the week (2-3 sentences) - focus on what the team accomplished
2. Major accomplishments (3-5 bullet points highlighting significant completed work)
3. Team performance summary (overall productivity, notable contributors, patterns)
4. Key focus areas for next week based on overdue items and patterns

Return a JSON object with:
{
  "overview": "Executive overview paragraph",
  "major_accomplishments": ["Accomplishment 1", "Accomplishment 2", ...],
  "team_summary": "Brief team performance paragraph including top contributors",
  "next_week_focus": ["Focus area 1", "Focus area 2", ...]
}

Focus on strategic insights and high-level accomplishments. Identify themes in the completed work.

IMPORTANT: Only return the JSON object, no additional text."""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[
                    {"role": "user", "content": f"{prompt}\n\nWeekly Data:\n{json.dumps(data_summary, indent=2)}"}
                ]
            )

            response_text = response.content[0].text.strip()

            # Parse JSON response
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            summary = json.loads(response_text)
            logger.info("Weekly summary generated successfully")
            return summary

        except Exception as e:
            logger.error(f"Error generating weekly summary: {e}")
            return {
                'overview': f"This week the team completed {len(completed_tasks)} tasks. There are {len(overdue_tasks)} overdue items.",
                'major_accomplishments': ['Weekly tasks completed as planned'],
                'team_summary': 'Team continues to make steady progress.',
                'next_week_focus': ['Continue current initiatives']
            }

    def _get_top_performers(self, completed_tasks: List[Dict[str, Any]], top_n: int = 5) -> List[Dict[str, Any]]:
        """Get top performers by number of completed tasks.

        Args:
            completed_tasks: List of completed tasks
            top_n: Number of top performers to return

        Returns:
            List of top performers with task counts
        """
        task_counts = {}
        for task in completed_tasks:
            assignee = task.get('assignee', 'Unassigned')
            task_counts[assignee] = task_counts.get(assignee, 0) + 1

        sorted_performers = sorted(task_counts.items(), key=lambda x: x[1], reverse=True)

        return [
            {'name': name, 'completed_tasks': count}
            for name, count in sorted_performers[:top_n]
        ]

    def analyze_task_patterns(self, completed_tasks: List[Dict[str, Any]],
                             overdue_tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze patterns in task completion and identify potential issues.

        Args:
            completed_tasks: List of completed tasks
            overdue_tasks: List of overdue tasks

        Returns:
            Dictionary with pattern analysis and recommendations
        """
        logger.info("Analyzing task patterns")

        # Group overdue tasks by assignee
        overdue_by_person = {}
        for task in overdue_tasks:
            assignee = task.get('assignee', 'Unassigned')
            if assignee not in overdue_by_person:
                overdue_by_person[assignee] = []
            overdue_by_person[assignee].append(task)

        # Identify people with many overdue tasks
        high_overdue = {
            person: len(tasks)
            for person, tasks in overdue_by_person.items()
            if len(tasks) >= 3
        }

        # Calculate completion rate by person
        completed_by_person = {}
        for task in completed_tasks:
            assignee = task.get('assignee', 'Unassigned')
            completed_by_person[assignee] = completed_by_person.get(assignee, 0) + 1

        return {
            'high_overdue_members': high_overdue,
            'top_completers': self._get_top_performers(completed_tasks, 3),
            'total_overdue': len(overdue_tasks),
            'total_completed': len(completed_tasks)
        }
