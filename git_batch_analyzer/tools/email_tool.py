import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from ..types import ToolResponse

logger = logging.getLogger(__name__)


class EmailTool:
    """Tool for sending emails via SMTP or Mailjet API."""

    def __init__(self, 
                 sender_email: str, 
                 sender_name: str, 
                 provider: str = "smtp",
                 api_key: Optional[str] = None, 
                 api_secret: Optional[str] = None,
                 smtp_server: Optional[str] = None,
                 smtp_port: int = 587,
                 smtp_password: Optional[str] = None):
        """
        Initialize EmailTool with either SMTP or Mailjet configuration.
        
        Args:
            sender_email: Email address to send from
            sender_name: Display name for sender
            provider: 'smtp' or 'mailjet'
            api_key: Mailjet API key or SMTP username (usually same as sender_email)
            api_secret: Mailjet API secret or SMTP password
            smtp_server: SMTP server hostname (e.g., smtp.gmail.com)
            smtp_port: SMTP port (default: 587 for TLS)
            smtp_password: SMTP password (alias for api_secret for clarity)
        """
        self.sender_email = sender_email
        self.sender_name = sender_name
        self.provider = provider.lower()
        
        if self.provider == "mailjet":
            try:
                from mailjet_rest import Client
                self.client = Client(auth=(api_key, api_secret), version='v3.1')
            except ImportError:
                raise ImportError("mailjet-rest package is required for Mailjet provider")
                
        elif self.provider == "smtp":
            self.smtp_server = smtp_server
            self.smtp_port = smtp_port
            self.smtp_username = api_key or sender_email
            self.smtp_password = smtp_password or api_secret
            
            if not self.smtp_server:
                raise ValueError("SMTP provider requires smtp_server")
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def send_email(self, recipients: List[str], subject: str, body: str) -> ToolResponse:
        """
        Sends an email to a list of recipients.

        Args:
            recipients: List of email addresses.
            subject: Email subject.
            body: Email body in HTML format.

        Returns:
            ToolResponse: Success or error response.
        """
        if not recipients:
            return ToolResponse.error_response("No recipients provided")

        if self.provider == "mailjet":
            return self._send_via_mailjet(recipients, subject, body)
        elif self.provider == "smtp":
            return self._send_via_smtp(recipients, subject, body)
        else:
            return ToolResponse.error_response(f"Unsupported provider: {self.provider}")

    def _send_via_mailjet(self, recipients: List[str], subject: str, body: str) -> ToolResponse:
        """Send email via Mailjet API."""
        data = {
            'Messages': [
                {
                    "From": {
                        "Email": self.sender_email,
                        "Name": self.sender_name
                    },
                    "To": [{"Email": email} for email in recipients],
                    "Subject": subject,
                    "HTMLPart": body
                }
            ]
        }

        try:
            result = self.client.send.create(data=data)
            if result.status_code == 200:
                logger.info(f"Email sent successfully via Mailjet to {', '.join(recipients)}")
                return ToolResponse.success_response("Email sent successfully via Mailjet")
            else:
                logger.error(f"Failed to send email via Mailjet: {result.status_code} {result.json()}")
                return ToolResponse.error_response(f"Failed to send email via Mailjet: {result.json()}")
        except Exception as e:
            logger.error(f"Error sending email via Mailjet: {e}")
            return ToolResponse.error_response(f"Error sending email via Mailjet: {e}")

    def _send_via_smtp(self, recipients: List[str], subject: str, body: str) -> ToolResponse:
        """Send email via SMTP."""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{self.sender_name} <{self.sender_email}>"
            msg['Subject'] = subject
            
            # Add HTML body
            html_part = MIMEText(body, 'html')
            msg.attach(html_part)
            
            # Connect to SMTP server
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                # Try TLS if not using standard relay port (25)
                if self.smtp_port != 25:
                    try:
                        server.starttls()  # Enable TLS encryption
                    except Exception as e:
                        logger.warning(f"TLS not supported or failed: {e}")
                
                # Try authentication if password provided
                if self.smtp_password:
                    try:
                        server.login(self.smtp_username, self.smtp_password)
                    except Exception as e:
                        logger.warning(f"Authentication failed or not required: {e}")
                
                # Send email to each recipient
                for recipient in recipients:
                    msg['To'] = recipient
                    text = msg.as_string()
                    server.sendmail(self.sender_email, [recipient], text)
                    del msg['To']  # Remove To header for next iteration
                
            logger.info(f"Email sent successfully via SMTP to {', '.join(recipients)}")
            return ToolResponse.success_response(f"Email sent successfully via SMTP to {len(recipients)} recipients")
            
        except Exception as e:
            logger.error(f"Error sending email via SMTP: {e}")
            return ToolResponse.error_response(f"Error sending email via SMTP: {e}")
