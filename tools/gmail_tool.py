"""Gmail tool for querying and reading emails using LLM for query understanding."""

import os
import pickle
from typing import Optional, Literal, List
from pathlib import Path
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from .base import BaseTool
from config import settings

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
except ImportError:
    print("Gmail dependencies not installed. Run: uv add google-auth-oauthlib google-auth-httplib2 google-api-python-client")


SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


class EmailQuery(BaseModel):
    """Parsed email query from natural language."""
    query_type: Literal["search", "recent", "unread", "from_sender", "subject"] = Field(
        description="Type of email query to perform"
    )
    search_terms: Optional[str] = Field(
        default=None,
        description="Search terms or keywords to look for in emails"
    )
    sender: Optional[str] = Field(
        default=None,
        description="Email sender to filter by (if query_type is 'from_sender')"
    )
    subject_filter: Optional[str] = Field(
        default=None,
        description="Subject keywords to filter by"
    )
    max_results: int = Field(
        default=5,
        description="Maximum number of emails to return (1-20)"
    )
    reasoning: str = Field(
        description="Brief explanation of the query interpretation"
    )


class GmailTool(BaseTool):
    """Tool for querying and reading Gmail emails using LLM parsing."""
    
    def __init__(self, enabled: bool = True):
        super().__init__(
            name="gmail",
            description="Search and read Gmail emails",
            capabilities=(
                "Can search your Gmail inbox, read recent emails, find unread messages, "
                "filter emails by sender, search by subject or keywords, retrieve specific emails. "
                "Understands queries like 'show my recent emails', 'find emails from john', "
                "'search for emails about project', 'do I have any unread emails', "
                "'what did sarah send me', 'show emails with receipt in subject'."
            ),
            enabled=enabled
        )
        self._init_agent()
        self.service = None
    
    def _init_agent(self):
        """Initialize the LLM agent for query understanding."""
        if settings.OPENAI_API_KEY:
            os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
        
        system_prompt = """You are a Gmail query analyzer. Parse natural language email queries and convert them to structured search parameters.

Query Types:
- "search": General keyword search in email content
- "recent": Get recent emails (no specific search)
- "unread": Find unread emails only
- "from_sender": Filter emails from specific sender
- "subject": Search by subject line keywords

Extract Information:
- search_terms: Keywords to search for in email body/subject
- sender: Email address or name of sender
- subject_filter: Keywords that should appear in subject
- max_results: Number of emails to return (default 5, max 20)

Examples:
- "show my recent emails" → query_type: "recent", max_results: 5
- "find emails from john" → query_type: "from_sender", sender: "john"
- "search for emails about project alpha" → query_type: "search", search_terms: "project alpha"
- "do I have unread emails" → query_type: "unread"
- "emails with invoice in subject" → query_type: "subject", subject_filter: "invoice"
- "last 10 emails from sarah" → query_type: "from_sender", sender: "sarah", max_results: 10
"""
        
        self.agent = Agent(
            model=OpenAIChatModel("gpt-4o-mini"),
            output_type=EmailQuery,
            system_prompt=system_prompt,
        )
    
    def _get_gmail_service(self):
        """Authenticate and return Gmail API service."""
        if self.service:
            return self.service
        
        creds = None
        token_path = Path("token.pickle")
        creds_path = Path("oauth2_credentials.json")
        
        # Load saved credentials
        if token_path.exists():
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
        
        # If no valid credentials, authenticate
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not creds_path.exists():
                    raise FileNotFoundError(
                        "oauth2_credentials.json not found. "
                        "Download it from Google Cloud Console."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(creds_path), SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            # Save credentials
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)
        
        self.service = build('gmail', 'v1', credentials=creds)
        return self.service
    
    async def process(self, text: str) -> Optional[str]:
        """
        Query Gmail based on LLM-parsed request.
        
        Args:
            text: User input requesting email information
            
        Returns:
            Formatted email results or None on error
        """
        try:
            # Use LLM to understand the query
            result = await self.agent.run(text)
            query: EmailQuery = result.output
            
            print(f"[Gmail] Query type: {query.query_type}")
            print(f"[Gmail] Reasoning: {query.reasoning}")
            
            # Get Gmail service
            service = self._get_gmail_service()
            
            # Build Gmail API query
            gmail_query = self._build_gmail_query(query)
            print(f"[Gmail] API query: {gmail_query}")
            
            # Execute search
            results = service.users().messages().list(
                userId='me',
                q=gmail_query,
                maxResults=min(query.max_results, 20)
            ).execute()
            
            messages = results.get('messages', [])
            
            if not messages:
                return "No emails found matching your query."
            
            # Get email details
            email_summaries = []
            for msg in messages[:query.max_results]:
                msg_data = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='metadata',
                    metadataHeaders=['From', 'Subject', 'Date']
                ).execute()
                
                headers = {h['name']: h['value'] for h in msg_data['payload']['headers']}
                email_summaries.append({
                    'from': headers.get('From', 'Unknown'),
                    'subject': headers.get('Subject', '(no subject)'),
                    'date': headers.get('Date', 'Unknown date')
                })
            
            # Format results
            return self._format_email_results(email_summaries, query)
            
        except FileNotFoundError as e:
            print(f"Gmail auth error: {e}")
            return "Gmail authentication required. Please ensure oauth2_credentials.json is in the project directory."
        except Exception as e:
            print(f"Gmail error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _build_gmail_query(self, query: EmailQuery) -> str:
        """Build Gmail API query string from parsed query."""
        parts = []
        
        if query.query_type == "unread":
            parts.append("is:unread")
        
        if query.query_type == "from_sender" and query.sender:
            parts.append(f"from:{query.sender}")
        
        if query.query_type == "subject" and query.subject_filter:
            parts.append(f"subject:{query.subject_filter}")
        
        if query.query_type == "search" and query.search_terms:
            parts.append(query.search_terms)
        
        # If no specific query, search all
        return " ".join(parts) if parts else ""
    
    def _format_email_results(self, emails: List[dict], query: EmailQuery) -> str:
        """Format email results for display."""
        if not emails:
            return "No emails found."
        
        result = f"Found {len(emails)} email(s):\n\n"
        
        for i, email in enumerate(emails, 1):
            result += f"{i}. From: {email['from']}\n"
            result += f"   Subject: {email['subject']}\n"
            result += f"   Date: {email['date']}\n\n"
            
        
        return result.strip()

