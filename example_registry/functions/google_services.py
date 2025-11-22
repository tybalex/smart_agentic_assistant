"""Google Services function implementations"""
import json
import random

def google_receive_membership_email() -> str:
    """Receive a membership email from Google"""
    name_pool = ["Alex", "Ben", "Charlie", "David", "Ethan", "Frank", "George", "Henry", "Isaac", "Jack", "Liam", "Mason", "Noah", "Oliver", "Parker", "Quinn", "Ryan", "Samuel", "Thomas", "William"]
    email_content = f"""
    Subject: Welcome to the Google Group,
    user name is {name_pool[random.randint(0, len(name_pool) - 1)]} {name_pool[random.randint(0, len(name_pool) - 1)]}, email is {name_pool[random.randint(0, len(name_pool) - 1)]}.{name_pool[random.randint(0, len(name_pool) - 1)]}@gmail.com,
    membership level is premium,
    join date is 2021-01-{random.randint(1, 31)},
    """
    
    return email_content


# In-memory mock of Google Sheets
# Structure: {sheet_id: {range: [[row1], [row2], ...]}}
_mock_sheets = {}

def google_sheets_append(sheet_id: str, range: str, values: list) -> str:
    """Append rows to a Google Sheet"""
    # Initialize sheet if it doesn't exist
    if sheet_id not in _mock_sheets:
        _mock_sheets[sheet_id] = {}
    
    # Initialize range if it doesn't exist
    if range not in _mock_sheets[sheet_id]:
        _mock_sheets[sheet_id][range] = []
    
    # Append the values
    _mock_sheets[sheet_id][range].extend(values)
    
    return f"Appended {len(values)} rows to {sheet_id}!{range}"


def google_sheets_read(sheet_id: str, range: str) -> str:
    """Read data from a Google Sheet"""
    # Return empty if sheet doesn't exist
    if sheet_id not in _mock_sheets:
        return "[]"
    
    # Return empty if range doesn't exist
    if range not in _mock_sheets[sheet_id]:
        return "[]"
    
    # Return the data as JSON string
    import json
    return json.dumps(_mock_sheets[sheet_id][range])


# In-memory mock of Google Groups
# Structure: {group_id: {member_email: role}}
_mock_groups = {
    "group_user1": {
        "admin1@example.com": "admin",
        "member2@example.com": "member",
        "member3@example.com": "member"
    },
    "group_user2": {
        "admin4@example.com": "admin",
        "member5@example.com": "member",
        "member6@example.com": "member"
    }
}

def google_groups_list_members(group_id: str) -> str:
    """List all members of a Google Group"""
    return json.dumps(_mock_groups[group_id])

def google_groups_add_member(group_id: str, member_email: str, role: str) -> str:
    """Add a new member to a Google Group"""
    _mock_groups[group_id][member_email] = role
    return f"Added {member_email} to {group_id} as {role}"

# In-memory mock of Gmail emails
# Structure: [{to: str, subject: str, body: str, attachments: list}]
_mock_emails = []

def gmail_send_email(to: str, subject: str, body: str, attachments: list = None) -> str:
    """Send an email via Gmail API"""
    _mock_emails.append({
        "to": to,
        "subject": subject,
        "body": body,
        "attachments": attachments
    })
    return f"Sent email to {to} with subject {subject} and body {body}"

def gmail_list_emails() -> str:
    """List all emails"""
    return json.dumps(_mock_emails)