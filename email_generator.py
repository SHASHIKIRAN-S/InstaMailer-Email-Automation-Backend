"""
Email Generation Service using External API
This module handles email content generation using an external API service.
"""

import requests
import json
import logging
from typing import Optional, Dict
from backend.config import get_settings

logger = logging.getLogger(__name__)


class EmailGenerator:
    """Email generation service using external API"""

    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.email_api_key
        self.api_url = self.settings.email_api_url
        self.api_model = getattr(self.settings, "email_api_model", "mistralai/mistral-7b-instruct")

    def generate_email_content(self, prompt: str, tone: str = "professional",
                               email_type: str = "general") -> Optional[str]:
        """
        Generate email content using external API

        Args:
            prompt: User's prompt/request for email content
            tone: Email tone (professional, casual, etc.)
            email_type: Type of email (general, business, etc.)

        Returns:
            Generated email content or None if failed
        """
        if not self.api_key or not self.api_url:
            logger.error("Email API key or URL not configured")
            return None

        try:
            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": f"Write a {tone} email about: {prompt}"
                            }
                        ]
                    }
                ]
            }

            headers = {
                "Content-Type": "application/json"
            }

            logger.info(f"Sending request to: {self.api_url}")
            logger.debug(f"Payload: {json.dumps(payload, indent=2)}")

            response = requests.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=30
            )

            logger.info(f"API Response Status: {response.status_code}")
            response.raise_for_status()

            data = response.json()
            logger.debug(f"Response Data: {json.dumps(data, indent=2)}")

            # Gemini's response format
            if "candidates" in data and data["candidates"]:
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()

            logger.error("No 'candidates' found in API response")
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            if e.response is not None:
                logger.error(f"Response content: {e.response.text}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse API response: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error generating email: {e}")
            return None

    def generate_email_with_subject(self, prompt: str, tone: str = "professional") -> Dict[str, str]:
        """
        Generate both email subject and content

        Args:
            prompt: User's prompt
            tone: Email tone

        Returns:
            Dictionary with 'subject' and 'content' keys
        """
        try:
            content = self.generate_email_content(prompt, tone)
            if not content:
                logger.warning("Failed to generate content, using prompt as fallback")
                return {"subject": "Email", "content": prompt}

            subject = self._extract_subject_from_content(content, prompt)
            return {"subject": subject, "content": content}

        except Exception as e:
            logger.error(f"Error generating email with subject: {e}")
            return {"subject": "Email", "content": prompt}

    def _extract_subject_from_content(self, content: str, prompt: str) -> str:
        """
        Extract or generate a subject line from content

        Args:
            content: Generated email content
            prompt: Original user prompt

        Returns:
            Subject line
        """
        try:
            lines = content.strip().split('\n')
            first_line = lines[0].strip()

            if len(first_line) < 100 and not first_line.lower().startswith("dear"):
                return first_line

            # Fallback to trimmed prompt
            words = prompt.strip().split()
            subject = " ".join(words[:7]) or "Email"
            return subject[:47] + "..." if len(subject) > 50 else subject

        except Exception as e:
            logger.warning(f"Error extracting subject: {e}")
            return "Email"
