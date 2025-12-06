"""Google Services function implementations"""
import json
import random

def google_receive_membership_email() -> str:
    """Receive a membership email from Google"""
    name_pool = ["Alex", "Ben", "Charlie", "David", "Ethan", "Frank", "George", "Henry", "Isaac", "Jack", "Liam", "Mason", "Noah", "Oliver", "Parker", "Quinn", "Ryan", "Samuel", "Thomas", "William"]
    first_name = name_pool[random.randint(0, len(name_pool) - 1)]
    last_name = name_pool[random.randint(0, len(name_pool) - 1)]
    email = f"{first_name.lower()}.{last_name.lower()}@gmail.com"
    
    return json.dumps({
        "success": True,
        "email_content": {
            "subject": "Welcome to the Google Group",
            "user_name": f"{first_name} {last_name}",
            "email": email,
            "membership_level": "premium",
            "join_date": f"2021-01-{random.randint(1, 31):02d}"
        }
    })


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
    
    return json.dumps({
        "success": True,
        "message": f"Appended {len(values)} rows to {sheet_id}!{range}",
        "rows_added": len(values),
        "total_rows": len(_mock_sheets[sheet_id][range])
    })


def google_sheets_read(sheet_id: str, range: str) -> str:
    """Read data from a Google Sheet"""
    # Return empty if sheet doesn't exist
    if sheet_id not in _mock_sheets:
        return json.dumps({
            "success": True,
            "data": [],
            "count": 0
        })
    
    # Return empty if range doesn't exist
    if range not in _mock_sheets[sheet_id]:
        return json.dumps({
            "success": True,
            "data": [],
            "count": 0
        })
    
    data = _mock_sheets[sheet_id][range]
    return json.dumps({
        "success": True,
        "data": data,
        "count": len(data)
    })


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
    if group_id not in _mock_groups:
        return json.dumps({
            "success": True,
            "members": [],
            "count": 0,
            "group_id": group_id
        })
    
    members = [{"email": email, "role": role} for email, role in _mock_groups[group_id].items()]
    return json.dumps({
        "success": True,
        "members": members,
        "count": len(members),
        "group_id": group_id
    })

def google_groups_add_member(group_id: str, member_email: str, role: str = "MEMBER") -> str:
    """Add a new member to a Google Group"""
    # Create group if it doesn't exist
    if group_id not in _mock_groups:
        _mock_groups[group_id] = {}
    
    # Check if already a member
    already_member = member_email in _mock_groups[group_id]
    _mock_groups[group_id][member_email] = role
    
    if already_member:
        return json.dumps({
            "success": True,
            "message": f"Updated {member_email} role to {role} in {group_id}",
            "action": "updated"
        })
    return json.dumps({
        "success": True,
        "message": f"Added {member_email} to {group_id} as {role}",
        "action": "added"
    })


# In-memory mock of Gmail emails
# Structure: [{to: str, subject: str, body: str, cc: list, attachments: list}]
_mock_emails = [
    {
        "id": "email_001",
        "from": "admin1@example.com",
        "to": "member2@example.com",
        "subject": "Test email",
        "body": "This is a test email",
        "cc": [],
        "attachments": []
    },
    {
        "id": "email_002",
        "from": "admin2@example.com",
        "to": "member3@example.com",
        "subject": "Test email",
        "body": "This is a test email",
        "cc": [],
        "attachments": []
    }
]

_email_counter = 3

def gmail_send_email(to: str, subject: str, body: str, cc: list = None, attachments: list = None) -> str:
    """Send an email via Gmail API"""
    global _email_counter
    
    email_id = f"email_{_email_counter:03d}"
    _email_counter += 1
    
    email = {
        "id": email_id,
        "to": to,
        "subject": subject,
        "body": body,
        "cc": cc or [],
        "attachments": attachments or []
    }
    _mock_emails.append(email)
    
    return json.dumps({
        "success": True,
        "message": f"Sent email to {to}" + (f" (CC: {', '.join(cc)})" if cc else "") + f" with subject '{subject}'",
        "email_id": email_id
    })

def gmail_list_emails() -> str:
    """List all emails"""
    return json.dumps({
        "success": True,
        "emails": _mock_emails,
        "count": len(_mock_emails)
    })
