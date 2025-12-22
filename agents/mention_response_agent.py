"""Mention Response Agent - Drafts suggested responses to unanswered @mentions using Claude."""
import json
from typing import List, Dict, Any, Optional
from anthropic import Anthropic
from config import Config
from utils import setup_logger

logger = setup_logger(__name__)


class MentionResponseAgent:
    """Agent that analyzes @mentions and drafts suggested responses."""

    def __init__(self):
        """Initialize the Mention Response Agent."""
        self.client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self.model = "claude-sonnet-4-5-20250929"  # Claude Sonnet 4.5 (Sep 2025)
        logger.info("MentionResponseAgent initialized")

    def draft_response(self, mention_data: Dict[str, Any]) -> Dict[str, Any]:
        """Draft a suggested response for an unanswered mention.

        Args:
            mention_data: Dictionary containing mention context including:
                - task_name: The task title
                - task_description: Task notes/description
                - author_name: Who wrote the comment
                - comment_text: The comment content
                - recent_comments: Last 5 comments for context

        Returns:
            Dictionary with:
                - suggested_response: The drafted response text
                - confidence: "high", "medium", or "low"
                - reasoning: Brief explanation of confidence level
                - action_needed: What action is being requested
        """
        try:
            # Build context from recent comments
            context = self._build_conversation_context(mention_data)

            prompt = f"""You are helping draft a response to an @mention in Asana. The person mentioned needs to respond to this comment.

## Task Information
- **Task:** {mention_data.get('task_name', 'Unknown')}
- **Project:** {mention_data.get('project_name', 'Unknown')}
- **Task Description:** {mention_data.get('task_description', 'No description')[:500]}

## The Comment Needing Response
**From {mention_data.get('author_name', 'Someone')}:**
"{mention_data.get('comment_text', 'No comment text')}"

## Recent Conversation Context
{context}

## Your Task
Draft a helpful, professional response that:
1. Acknowledges what the person is asking or requesting
2. Provides a substantive response if possible
3. Indicates any follow-up actions needed

If there's NOT enough context to draft a meaningful response, indicate that with low confidence.

Return a JSON object:
{{
  "suggested_response": "Your drafted response text here (keep it concise, 1-3 sentences)",
  "confidence": "high/medium/low",
  "reasoning": "Brief explanation of your confidence level (1 sentence)",
  "action_needed": "Brief description of what action is being requested (1 sentence)"
}}

Confidence guidelines:
- **high**: Clear question/request with obvious answer based on context
- **medium**: Request is clear but response may need modification
- **low**: Ambiguous request or insufficient context to draft meaningful response

IMPORTANT: Only return the JSON object, no additional text."""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text.strip()

            # Parse JSON response
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            result = json.loads(response_text)
            logger.info(f"Drafted response with {result.get('confidence')} confidence for task: {mention_data.get('task_name', 'Unknown')[:50]}")
            return result

        except Exception as e:
            logger.error(f"Error drafting response: {e}")
            return {
                'suggested_response': None,
                'confidence': 'low',
                'reasoning': f'Error generating response: {str(e)}',
                'action_needed': 'Manual review required'
            }

    def _build_conversation_context(self, mention_data: Dict[str, Any]) -> str:
        """Build a string of recent conversation context.

        Args:
            mention_data: Dictionary containing recent_comments list

        Returns:
            Formatted string of recent comments
        """
        recent = mention_data.get('recent_comments', [])
        if not recent:
            return "No recent conversation history available"

        context_lines = []
        # Show last 3 comments before the mention for context
        for comment in recent[-4:-1]:  # Exclude the last one which is the mention itself
            author = comment.get('author_name', 'Unknown')
            text = comment.get('text', '')[:250]  # Truncate long comments
            if text:
                context_lines.append(f"- **{author}**: {text}")

        if not context_lines:
            return "No prior conversation context"

        return '\n'.join(context_lines)

    def batch_draft_responses(
        self,
        mentions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Draft responses for multiple mentions.

        Args:
            mentions: List of mention data dictionaries

        Returns:
            Same list with suggested_response, response_confidence, and action_needed added
        """
        logger.info(f"Drafting responses for {len(mentions)} unanswered mentions")

        for mention in mentions:
            response_data = self.draft_response(mention)
            mention['suggested_response'] = response_data.get('suggested_response')
            mention['response_confidence'] = response_data.get('confidence')
            mention['action_needed'] = response_data.get('action_needed')
            mention['response_reasoning'] = response_data.get('reasoning')

        # Log summary
        high_confidence = sum(1 for m in mentions if m.get('response_confidence') == 'high')
        medium_confidence = sum(1 for m in mentions if m.get('response_confidence') == 'medium')
        low_confidence = sum(1 for m in mentions if m.get('response_confidence') == 'low')

        logger.info(f"Response drafts complete: {high_confidence} high, {medium_confidence} medium, {low_confidence} low confidence")

        return mentions
