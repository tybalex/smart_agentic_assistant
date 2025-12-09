"""
Function implementations for the registry.
All functions are organized by service category.
"""

# Google Services
from .google_services import (
    google_sheets_append,
    google_sheets_read,
    google_groups_add_member,
    google_groups_list_members,
    gmail_send_email,
    gmail_list_emails,
    google_receive_membership_email
)

# Mailing List
from .mailing_list import (
    get_mailing_list,
    add_to_mailing_list,
    remove_from_mailing_list,
    list_all_mailing_lists,
    create_mailing_list
)

# Member Desk
from .member_desk import (
    member_desk_invite,
    member_desk_list_invitations,
    member_desk_accept_invitation,
    member_desk_get_invitation_status
)

# Salesforce
from .salesforce import (
    salesforce_query,
    salesforce_create,
    salesforce_describe_object,
    salesforce_list_objects
)

# Slack
from .slack import (
    slack_invite_to_channel,
    slack_send_message,
    slack_create_channel,
    slack_list_channels,
    slack_get_channel_info,
    slack_remove_user_from_channel,
    slack_list_messages,
    slack_list_users,
    slack_get_user_info,
    slack_invite_user
)

# GitHub
from .github import (
    github_create_branch,
    github_commit_file,
    github_create_pr,
    github_list_branches,
    github_list_prs,
    github_get_file,
    github_merge_pr
)

# Email (Mailchimp)
from .email import (
    mailchimp_add_subscriber,
    mailchimp_remove_subscriber
)

# Storage
from .storage import (
    fetch_file,
    upload_file
)

# Database
from .database import (
    postgres_query,
    postgres_insert
)

# HTTP
from .http import (
    http_request,
    send_webhook
)

# Notion
from .notion import (
    notion_create_page,
    notion_query_database,
    notion_update_page,
    notion_create_database
)

# AWS
from .aws import (
    aws_s3_upload,
    aws_s3_download,
    aws_lambda_invoke,
    aws_dynamodb_put,
    aws_dynamodb_query
)

# Airtable
from .airtable import (
    airtable_create_record,
    airtable_list_records,
    airtable_update_record
)

# Web
from .web import (
    # firecrawl_scrape,  # TODO: cleanup needed
    firecrawl_search,
    tavily_search,
    # tavily_extract,  # TODO: cleanup needed
)

# Payment (Stripe)
from .payment import (
    stripe_create_charge,
    stripe_create_customer
)

# Communication (Twilio)
from .communication import (
    twilio_send_sms,
    twilio_make_call
)

# AI (OpenAI)
from .ai import (
    openai_chat_completion,
    openai_embeddings
)

# Support (Zendesk)
from .support import (
    zendesk_create_ticket,
    zendesk_get_ticket,
    zendesk_update_ticket,
    zendesk_add_comment,
    zendesk_list_tickets,
    zendesk_search_tickets,
    zendesk_close_ticket
)


# Function mapping - maps function names to actual function objects
FUNCTION_MAP = {
    # Google Services
    "google_sheets_append": google_sheets_append,
    "google_sheets_read": google_sheets_read,
    "google_groups_add_member": google_groups_add_member,
    "google_groups_list_members": google_groups_list_members,
    "gmail_send_email": gmail_send_email,
    "gmail_list_emails": gmail_list_emails,
    "google_receive_membership_email": google_receive_membership_email,
    
    # Salesforce
    "salesforce_query": salesforce_query,
    "salesforce_create": salesforce_create,
    "salesforce_describe_object": salesforce_describe_object,
    "salesforce_list_objects": salesforce_list_objects,
    
    # Mailing List
    "get_mailing_list": get_mailing_list,
    "add_to_mailing_list": add_to_mailing_list,
    "remove_from_mailing_list": remove_from_mailing_list,
    "list_all_mailing_lists": list_all_mailing_lists,
    "create_mailing_list": create_mailing_list,
    
    # Member Desk
    "member_desk_invite": member_desk_invite,
    "member_desk_list_invitations": member_desk_list_invitations,
    "member_desk_accept_invitation": member_desk_accept_invitation,
    "member_desk_get_invitation_status": member_desk_get_invitation_status,
    
    # Slack
    "slack_invite_to_channel": slack_invite_to_channel,
    "slack_send_message": slack_send_message,
    "slack_create_channel": slack_create_channel,
    "slack_list_channels": slack_list_channels,
    "slack_get_channel_info": slack_get_channel_info,
    "slack_remove_user_from_channel": slack_remove_user_from_channel,
    "slack_list_messages": slack_list_messages,
    "slack_list_users": slack_list_users,
    "slack_get_user_info": slack_get_user_info,
    "slack_invite_user": slack_invite_user,
    
    # GitHub
    "github_create_branch": github_create_branch,
    "github_commit_file": github_commit_file,
    "github_create_pr": github_create_pr,
    "github_list_branches": github_list_branches,
    "github_list_prs": github_list_prs,
    "github_get_file": github_get_file,
    "github_merge_pr": github_merge_pr,
    
    # Email
    "mailchimp_add_subscriber": mailchimp_add_subscriber,
    "mailchimp_remove_subscriber": mailchimp_remove_subscriber,
    
    # Storage
    "fetch_file": fetch_file,
    "upload_file": upload_file,
    
    # Database
    "postgres_query": postgres_query,
    "postgres_insert": postgres_insert,
    
    # HTTP
    "http_request": http_request,
    "send_webhook": send_webhook,
    
    # Notion
    "notion_create_page": notion_create_page,
    "notion_query_database": notion_query_database,
    "notion_update_page": notion_update_page,
    "notion_create_database": notion_create_database,
    
    # AWS
    "aws_s3_upload": aws_s3_upload,
    "aws_s3_download": aws_s3_download,
    "aws_lambda_invoke": aws_lambda_invoke,
    "aws_dynamodb_put": aws_dynamodb_put,
    "aws_dynamodb_query": aws_dynamodb_query,
    
    # Airtable
    "airtable_create_record": airtable_create_record,
    "airtable_list_records": airtable_list_records,
    "airtable_update_record": airtable_update_record,
    
    # Web
    # "firecrawl_scrape": firecrawl_scrape,  # TODO: cleanup needed
    "firecrawl_search": firecrawl_search,
    "tavily_search": tavily_search,
    # "tavily_extract": tavily_extract,  # TODO: cleanup needed
    
    # Payment
    "stripe_create_charge": stripe_create_charge,
    "stripe_create_customer": stripe_create_customer,
    
    # Communication
    "twilio_send_sms": twilio_send_sms,
    "twilio_make_call": twilio_make_call,
    
    # AI
    "openai_chat_completion": openai_chat_completion,
    "openai_embeddings": openai_embeddings,
    
    # Support
    "zendesk_create_ticket": zendesk_create_ticket,
    "zendesk_get_ticket": zendesk_get_ticket,
    "zendesk_update_ticket": zendesk_update_ticket,
    "zendesk_add_comment": zendesk_add_comment,
    "zendesk_list_tickets": zendesk_list_tickets,
    "zendesk_search_tickets": zendesk_search_tickets,
    "zendesk_close_ticket": zendesk_close_ticket,
}


def get_function(function_name: str):
    """
    Get a function by name
    
    Args:
        function_name: Name of the function to retrieve
        
    Returns:
        The function object or None if not found
    """
    return FUNCTION_MAP.get(function_name)


__all__ = [
    # Google Services
    "google_sheets_append",
    "google_sheets_read",
    "google_groups_add_member",
    "google_groups_list_members",
    "gmail_send_email",
    "gmail_list_emails",
    "google_receive_membership_email",
    
    # Mailing List
    "get_mailing_list",
    "add_to_mailing_list",
    "remove_from_mailing_list",
    "list_all_mailing_lists",
    "create_mailing_list",
    
    # Member Desk
    "member_desk_invite",
    "member_desk_list_invitations",
    "member_desk_accept_invitation",
    "member_desk_get_invitation_status",
    
    # Salesforce
    "salesforce_query",
    "salesforce_create",
    "salesforce_describe_object",
    "salesforce_list_objects",
    
    # Slack
    "slack_invite_to_channel",
    "slack_send_message",
    "slack_create_channel",
    "slack_list_channels",
    "slack_get_channel_info",
    "slack_remove_user_from_channel",
    "slack_list_messages",
    "slack_list_users",
    "slack_get_user_info",
    "slack_invite_user",
    
    # GitHub
    "github_create_branch",
    "github_commit_file",
    "github_create_pr",
    "github_list_branches",
    "github_list_prs",
    "github_get_file",
    "github_merge_pr",
    
    # Email
    "mailchimp_add_subscriber",
    "mailchimp_remove_subscriber",
    
    # Storage
    "fetch_file",
    "upload_file",
    
    # Database
    "postgres_query",
    "postgres_insert",
    
    # HTTP
    "http_request",
    "send_webhook",
    
    # Notion
    "notion_create_page",
    "notion_query_database",
    "notion_update_page",
    "notion_create_database",
    
    # AWS
    "aws_s3_upload",
    "aws_s3_download",
    "aws_lambda_invoke",
    "aws_dynamodb_put",
    "aws_dynamodb_query",
    
    # Airtable
    "airtable_create_record",
    "airtable_list_records",
    "airtable_update_record",
    
    # Web
    # "firecrawl_scrape",  # TODO: cleanup needed
    "firecrawl_search",
    "tavily_search",
    # "tavily_extract",  # TODO: cleanup needed
    
    # Payment
    "stripe_create_charge",
    "stripe_create_customer",
    
    # Communication
    "twilio_send_sms",
    "twilio_make_call",
    
    # AI
    "openai_chat_completion",
    "openai_embeddings",
    
    # Support
    "zendesk_create_ticket",
    "zendesk_get_ticket",
    "zendesk_update_ticket",
    "zendesk_add_comment",
    "zendesk_list_tickets",
    "zendesk_search_tickets",
    "zendesk_close_ticket",
    
    # Utilities
    "FUNCTION_MAP",
    "get_function",
]

