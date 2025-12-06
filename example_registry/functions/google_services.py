"""Google Services function implementations"""
import json
import random

def google_receive_membership_email() -> str:
    """Receive a membership email notification for a new member organization
The email includes:
- Company name
- Membership level (End User Supporter, Silver, Gold, Platinum, etc.)
- Join date
- Region (Standard, China, Korea)
- Multiple contact types with their information:
  - Primary contact (name, email, role)
  - Technical contact (name, email, role)
  - Marketing contact (name, email, role)
    """
    
    # Random data pools
    first_names = ["Sarah", "James", "Emily", "Michael", "Jennifer", "David", "Lisa", "Robert", "Amanda", "William", "Jessica", "Daniel", "Ashley", "Christopher", "Nicole", "Andrew", "Stephanie", "Kevin", "Michelle", "Brian"]
    last_names = ["Chen", "Rodriguez", "Watson", "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Martinez", "Wilson", "Anderson", "Taylor", "Thomas", "Moore", "Jackson", "Martin", "Lee"]
    
    companies = [
        ("Acorn Technologies Inc.", "acorntech.io"),
        ("CloudScale Systems", "cloudscale.com"),
        ("DataFlow Analytics", "dataflow.io"),
        ("Quantum Computing Labs", "quantumlabs.tech"),
        ("NextGen Software", "nextgensoft.com"),
        ("Alpine Data Solutions", "alpinedata.io"),
        ("Velocity Networks", "velocitynet.com"),
        ("Stellar Innovations", "stellarinno.tech"),
        ("BlueSky Technologies", "blueskytech.io"),
        ("RedPoint Systems", "redpointsys.com"),
        ("GreenLeaf Software", "greenleafsoft.com"),
        ("OceanView Analytics", "oceanview.io"),
    ]
    
    membership_levels = ["End User Supporter", "Silver", "Gold", "Platinum"]
    regions = ["Standard", "China", "Korea"]
    
    primary_roles = ["VP of Engineering", "CTO", "Director of Engineering", "Head of Platform", "Chief Architect"]
    technical_roles = ["Senior DevOps Engineer", "Principal Engineer", "Staff Engineer", "Infrastructure Lead", "Platform Engineer"]
    marketing_roles = ["Marketing Director", "VP of Marketing", "Head of Developer Relations", "Community Manager", "Marketing Manager"]
    
    # Generate random company
    company_name, domain = random.choice(companies)
    
    # Generate random contacts
    def generate_contact(roles):
        first = random.choice(first_names)
        last = random.choice(last_names)
        role = random.choice(roles)
        email_name = f"{first.lower()}.{last.lower()[0]}"
        return {
            "name": f"{first} {last}",
            "email": f"{email_name}@{domain}",
            "role": role
        }
    
    # Generate join date (random date in 2024-2025)
    year = random.choice([2024, 2025])
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    join_date = f"{year}-{month:02d}-{day:02d}"
    
    return json.dumps({
        "success": True,
        "email_content": {
            "subject": f"New Member Notification: {company_name}",
            "company_name": company_name,
            "membership_level": random.choice(membership_levels),
            "join_date": join_date,
            "region": random.choice(regions),
            "end_user_qualified": random.choice([True, False]),
            "contacts": {
                "primary": generate_contact(primary_roles),
                "technical": generate_contact(technical_roles),
                "marketing": generate_contact(marketing_roles)
            }
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
