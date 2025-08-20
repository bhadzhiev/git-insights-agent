import logging
import smtplib
import time
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional, Dict
from ..types import ToolResponse

logger = logging.getLogger(__name__)


class EmailTool:
    """Tool for sending emails via SMTP."""

    def __init__(self, 
                 sender_email: str, 
                 sender_name: str, 
                 provider: str = "smtp",
                 api_key: Optional[str] = None, 
                 api_secret: Optional[str] = None,
                 smtp_server: Optional[str] = None,
                 smtp_port: int = 587,
                 smtp_password: Optional[str] = None,
                 email_mappings: Optional[Dict[str, str]] = None,
                 manager_email: Optional[str] = None):
        """
        Initialize EmailTool with SMTP configuration.
        
        Args:
            sender_email: Email address to send from
            sender_name: Display name for sender
            provider: Must be 'smtp' (legacy parameter, kept for compatibility)
            api_key: SMTP username (usually same as sender_email)
            api_secret: SMTP password
            smtp_server: SMTP server hostname (e.g., smtp.gmail.com)
            smtp_port: SMTP port (default: 587 for TLS)
            smtp_password: SMTP password (alias for api_secret for clarity)
            email_mappings: Dictionary mapping git commit emails to real email addresses
            manager_email: Manager email to CC on all reports (optional)
        """
        self.sender_email = sender_email
        self.sender_name = sender_name
        self.provider = provider.lower()
        self.email_mappings = email_mappings or {}
        self.manager_email = manager_email
        
        if self.provider != "smtp":
            raise ValueError("Only SMTP provider is supported")
            
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_username = api_key or sender_email
        self.smtp_password = smtp_password or api_secret
        
        if not self.smtp_server:
            raise ValueError("SMTP provider requires smtp_server")

    def send_email(self, recipients: List[str], subject: str, body: str, max_retries: int = 3) -> ToolResponse:
        """
        Sends an email to a list of recipients with retry mechanism.

        Args:
            recipients: List of email addresses.
            subject: Email subject.
            body: Email body in HTML format.
            max_retries: Maximum number of retry attempts (default: 3).

        Returns:
            ToolResponse: Success or error response.
        """
        if not recipients:
            return ToolResponse.error_response("No recipients provided")

        # Use email mapping if provided, otherwise use original recipients
        if self.email_mappings:
            final_recipients = self.map_recipients(recipients)
        else:
            final_recipients = recipients

        # Retry mechanism
        last_error = None
        for attempt in range(max_retries):
            try:
                result = self._send_via_smtp(final_recipients, subject, body)
                
                if result.success:
                    if attempt > 0:
                        logger.info(f"Email sent successfully on attempt {attempt + 1}")
                    return result
                else:
                    last_error = result.error
                    
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Email send attempt {attempt + 1} failed: {e}")
            
            # Wait before retry (exponential backoff)
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                logger.info(f"Retrying email send in {wait_time} seconds...")
                time.sleep(wait_time)
        
        return ToolResponse.error_response(f"Failed to send email after {max_retries} attempts. Last error: {last_error}")

    def map_email(self, email: str) -> str:
        """
        Map a git commit email to a real email address using configured mappings.
        
        Supports:
        1. Exact matches: "42930404+VeselinUzunov@users.noreply.github.com" -> "veselin.uzunov@linkin.eu"
        2. Pattern-based GitHub noreply mapping: Extract username and convert to real email
        3. Passthrough: If no mapping found, return original email
        
        Args:
            email: Original git commit email
            
        Returns:
            Mapped email address or original email if no mapping found
        """
        if not email:
            return email
            
        original_email = email
        
        # First try exact match from configuration
        if email in self.email_mappings:
            mapped_email = self.email_mappings[email]
            logger.debug(f"Email mapped (exact): {original_email} -> {mapped_email}")
            return mapped_email
        
        # Try GitHub noreply pattern matching: number+username@users.noreply.github.com
        github_pattern = r'^(\d+\+)?([^@]+)@users\.noreply\.github\.com$'
        match = re.match(github_pattern, email)
        
        if match:
            github_username = match.group(2)
            
            # Look for mapping based on GitHub username
            for commit_email, real_email in self.email_mappings.items():
                # Check if the mapping key contains this username
                if github_username.lower() in commit_email.lower():
                    logger.debug(f"Email mapped (GitHub pattern): {original_email} -> {real_email} (via username: {github_username})")
                    return real_email
            
            # If no specific mapping found, try to construct a reasonable email
            # Convert GitHub username to potential email format
            username_lower = github_username.lower()
            
            # Look for partial matches in mappings (e.g., if username is "VeselinUzunov", look for "veselin" in mappings)
            for commit_email, real_email in self.email_mappings.items():
                if any(part.lower() in real_email.lower() for part in [username_lower, github_username]):
                    logger.debug(f"Email mapped (partial match): {original_email} -> {real_email} (via partial username match)")
                    return real_email
        
        # No mapping found, return original email
        logger.debug(f"Email not mapped, using original: {original_email}")
        return email
    
    def map_recipients(self, recipients: List[str]) -> List[str]:
        """
        Map a list of recipient emails using the email mapping configuration.
        
        Args:
            recipients: List of original email addresses
            
        Returns:
            List of mapped email addresses with duplicates removed
        """
        if not recipients:
            return recipients
            
        mapped_recipients = []
        mapping_stats = {"mapped": 0, "unchanged": 0, "total": len(recipients)}
        
        for recipient in recipients:
            mapped = self.map_email(recipient)
            mapped_recipients.append(mapped)
            
            if mapped != recipient:
                mapping_stats["mapped"] += 1
                logger.info(f"Mapped recipient: {recipient} -> {mapped}")
            else:
                mapping_stats["unchanged"] += 1
        
        # Remove duplicates while preserving order
        unique_recipients = list(dict.fromkeys(mapped_recipients))
        
        if len(unique_recipients) != len(mapped_recipients):
            logger.info(f"Removed {len(mapped_recipients) - len(unique_recipients)} duplicate recipients after mapping")
        
        if mapping_stats["mapped"] > 0:
            logger.info(f"Email mapping summary: {mapping_stats['mapped']} mapped, {mapping_stats['unchanged']} unchanged, {len(unique_recipients)} unique recipients")
        
        return unique_recipients

    def _send_via_smtp(self, recipients: List[str], subject: str, body: str) -> ToolResponse:
        """Send email via SMTP with improved error handling, rate limiting, and CC support."""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{self.sender_name} <{self.sender_email}>"
            msg['Subject'] = subject
            
            # Add CC if manager email is configured
            if self.manager_email:
                msg['Cc'] = self.manager_email
                logger.debug(f"Adding manager to CC: {self.manager_email}")
            
            # Add HTML body
            html_part = MIMEText(body, 'html')
            msg.attach(html_part)
            
            # Connect to SMTP server with timeout
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30) as server:
                server.set_debuglevel(0)  # Disable debug output for cleaner logs
                
                # Try TLS if not using standard relay port (25)
                if self.smtp_port != 25:
                    try:
                        server.starttls()  # Enable TLS encryption
                        logger.debug("TLS encryption enabled")
                    except Exception as e:
                        logger.warning(f"TLS not supported or failed: {e}")
                        # For some servers, TLS failure is not critical
                
                # Authenticate if credentials provided
                authentication_required = False
                if self.smtp_password:
                    try:
                        server.login(self.smtp_username, self.smtp_password)
                        logger.debug(f"SMTP authentication successful for {self.smtp_username}")
                        authentication_required = True
                    except smtplib.SMTPAuthenticationError as e:
                        logger.error(f"SMTP authentication failed for {self.smtp_username}: {e}")
                        return ToolResponse.error_response(f"SMTP authentication failed: {e}")
                    except smtplib.SMTPException as e:
                        logger.warning(f"SMTP authentication error (may not be required): {e}")
                        # Some servers don't require auth, continue
                
                # Test connection with NOOP command
                try:
                    server.noop()
                    logger.debug("SMTP connection test successful")
                except Exception as e:
                    logger.warning(f"SMTP connection test failed: {e}")
                
                # Send email to each recipient with rate limiting
                sent_count = 0
                failed_recipients = []
                
                for i, recipient in enumerate(recipients):
                    try:
                        # Rate limiting: small delay between sends to avoid triggering spam filters
                        if i > 0:
                            time.sleep(0.5)  # 500ms delay between emails
                        
                        msg['To'] = recipient
                        text = msg.as_string()
                        
                        # Prepare all recipients (To + CC)
                        all_recipients = [recipient]
                        if self.manager_email:
                            all_recipients.append(self.manager_email)
                        
                        # Send the email
                        refused = server.sendmail(self.sender_email, all_recipients, text)
                        
                        if refused:
                            logger.warning(f"Email to {recipient} was refused: {refused}")
                            failed_recipients.append(recipient)
                        else:
                            sent_count += 1
                            if self.manager_email:
                                logger.debug(f"Email sent successfully to {recipient} (CC: {self.manager_email})")
                            else:
                                logger.debug(f"Email sent successfully to {recipient}")
                        
                        del msg['To']  # Remove To header for next iteration
                        
                    except smtplib.SMTPRecipientsRefused as e:
                        logger.warning(f"Recipient {recipient} was refused: {e}")
                        failed_recipients.append(recipient)
                    except smtplib.SMTPException as e:
                        logger.warning(f"SMTP error sending to {recipient}: {e}")
                        failed_recipients.append(recipient)
                    except Exception as e:
                        logger.warning(f"Unexpected error sending to {recipient}: {e}")
                        failed_recipients.append(recipient)
                
                # Evaluate results
                cc_info = f" (CC: {self.manager_email})" if self.manager_email else ""
                
                if sent_count == 0:
                    return ToolResponse.error_response(f"Failed to send email to any recipients{cc_info}. Failed: {failed_recipients}")
                elif failed_recipients:
                    logger.warning(f"Email sent to {sent_count}/{len(recipients)} recipients{cc_info}. Failed: {failed_recipients}")
                    return ToolResponse.success_response(f"Email sent to {sent_count}/{len(recipients)} recipients{cc_info}. Some failures occurred.")
                else:
                    logger.info(f"Email sent successfully via SMTP to all {sent_count} recipients{cc_info}")
                    return ToolResponse.success_response(f"Email sent successfully via SMTP to all {sent_count} recipients{cc_info}")
                
        except smtplib.SMTPConnectError as e:
            logger.error(f"Failed to connect to SMTP server {self.smtp_server}:{self.smtp_port}: {e}")
            return ToolResponse.error_response(f"SMTP connection failed: {e}")
        except smtplib.SMTPServerDisconnected as e:
            logger.error(f"SMTP server disconnected unexpectedly: {e}")
            return ToolResponse.error_response(f"SMTP server disconnected: {e}")
        except Exception as e:
            logger.error(f"Unexpected error sending email via SMTP: {e}")
            return ToolResponse.error_response(f"SMTP error: {e}")
