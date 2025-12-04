"""Support ticketing function implementations (Zendesk)"""
import json
from datetime import datetime
from typing import Optional, List

# In-memory mock storage for Zendesk tickets
_mock_zendesk_tickets = {
    "1001": {
        "id": "1001",
        "subject": "Cannot login to account",
        "description": "User reports being unable to login after password reset",
        "priority": "high",
        "status": "open",
        "requester_email": "user1@example.com",
        "assignee": "support-agent-1",
        "tags": ["login", "password", "urgent"],
        "comments": [
            {"author": "user1@example.com", "body": "I reset my password but still can't login", "created_at": "2024-01-15T10:00:00Z"},
            {"author": "support-agent-1", "body": "We're looking into this issue", "created_at": "2024-01-15T10:30:00Z"}
        ],
        "created_at": "2024-01-15T10:00:00Z",
        "updated_at": "2024-01-15T10:30:00Z"
    },
    "1002": {
        "id": "1002",
        "subject": "Billing question",
        "description": "Question about invoice from last month",
        "priority": "normal",
        "status": "pending",
        "requester_email": "billing@acme.com",
        "assignee": "support-agent-2",
        "tags": ["billing", "invoice"],
        "comments": [
            {"author": "billing@acme.com", "body": "Can you explain line item #3?", "created_at": "2024-01-14T14:00:00Z"}
        ],
        "created_at": "2024-01-14T14:00:00Z",
        "updated_at": "2024-01-14T14:00:00Z"
    },
    "1003": {
        "id": "1003",
        "subject": "Feature request: Dark mode",
        "description": "Would love to have a dark mode option in the app",
        "priority": "low",
        "status": "solved",
        "requester_email": "poweruser@techcorp.com",
        "assignee": "support-agent-1",
        "tags": ["feature-request", "ui"],
        "comments": [
            {"author": "poweruser@techcorp.com", "body": "Dark mode would reduce eye strain", "created_at": "2024-01-10T09:00:00Z"},
            {"author": "support-agent-1", "body": "Great suggestion! We've added this to our roadmap.", "created_at": "2024-01-10T11:00:00Z"},
            {"author": "support-agent-1", "body": "Dark mode has been released in v2.5!", "created_at": "2024-01-20T15:00:00Z"}
        ],
        "created_at": "2024-01-10T09:00:00Z",
        "updated_at": "2024-01-20T15:00:00Z"
    }
}

_ticket_id_counter = 1004


def zendesk_create_ticket(
    subject: str,
    description: str,
    priority: str = "normal",
    requester_email: str = None,
    tags: List[str] = None
) -> str:
    """Create a support ticket in Zendesk
    
    Args:
        subject: The ticket subject/title
        description: Detailed description of the issue
        priority: Ticket priority (low, normal, high, urgent). Defaults to normal.
        requester_email: Email of the person requesting support
        tags: List of tags to categorize the ticket
    
    Returns:
        JSON string with the created ticket details
    """
    global _ticket_id_counter
    
    ticket_id = str(_ticket_id_counter)
    _ticket_id_counter += 1
    
    now = datetime.utcnow().isoformat() + "Z"
    
    ticket = {
        "id": ticket_id,
        "subject": subject,
        "description": description,
        "priority": priority or "normal",
        "status": "new",
        "requester_email": requester_email,
        "assignee": None,
        "tags": tags or [],
        "comments": [],
        "created_at": now,
        "updated_at": now
    }
    
    _mock_zendesk_tickets[ticket_id] = ticket
    
    return json.dumps({
        "success": True,
        "ticket": ticket
    })


def zendesk_get_ticket(ticket_id: str) -> str:
    """Get a specific Zendesk ticket by ID
    
    Args:
        ticket_id: The ticket ID to retrieve
    
    Returns:
        JSON string with ticket details or error if not found
    """
    ticket = _mock_zendesk_tickets.get(ticket_id)
    
    if not ticket:
        return json.dumps({
            "success": False,
            "error": f"Ticket {ticket_id} not found"
        })
    
    return json.dumps({
        "success": True,
        "ticket": ticket
    })


def zendesk_update_ticket(
    ticket_id: str,
    status: str = None,
    priority: str = None,
    assignee: str = None,
    tags: List[str] = None
) -> str:
    """Update a Zendesk ticket
    
    Args:
        ticket_id: The ticket ID to update
        status: New status (new, open, pending, hold, solved, closed)
        priority: New priority (low, normal, high, urgent)
        assignee: Assign ticket to an agent
        tags: Replace tags with new list
    
    Returns:
        JSON string with updated ticket details
    """
    ticket = _mock_zendesk_tickets.get(ticket_id)
    
    if not ticket:
        return json.dumps({
            "success": False,
            "error": f"Ticket {ticket_id} not found"
        })
    
    if status:
        ticket["status"] = status
    if priority:
        ticket["priority"] = priority
    if assignee:
        ticket["assignee"] = assignee
    if tags is not None:
        ticket["tags"] = tags
    
    ticket["updated_at"] = datetime.utcnow().isoformat() + "Z"
    
    return json.dumps({
        "success": True,
        "ticket": ticket
    })


def zendesk_add_comment(ticket_id: str, comment: str, author: str = "system") -> str:
    """Add a comment to a Zendesk ticket
    
    Args:
        ticket_id: The ticket ID to comment on
        comment: The comment text
        author: Who is adding the comment (email or name)
    
    Returns:
        JSON string with success status and updated comments
    """
    ticket = _mock_zendesk_tickets.get(ticket_id)
    
    if not ticket:
        return json.dumps({
            "success": False,
            "error": f"Ticket {ticket_id} not found"
        })
    
    now = datetime.utcnow().isoformat() + "Z"
    
    new_comment = {
        "author": author,
        "body": comment,
        "created_at": now
    }
    
    ticket["comments"].append(new_comment)
    ticket["updated_at"] = now
    
    return json.dumps({
        "success": True,
        "comment": new_comment,
        "total_comments": len(ticket["comments"])
    })


def zendesk_list_tickets(
    status: str = None,
    priority: str = None,
    assignee: str = None
) -> str:
    """List Zendesk tickets with optional filters
    
    Args:
        status: Filter by status (new, open, pending, hold, solved, closed)
        priority: Filter by priority (low, normal, high, urgent)
        assignee: Filter by assignee
    
    Returns:
        JSON string with list of tickets matching filters
    """
    tickets = list(_mock_zendesk_tickets.values())
    
    if status:
        tickets = [t for t in tickets if t["status"] == status]
    if priority:
        tickets = [t for t in tickets if t["priority"] == priority]
    if assignee:
        tickets = [t for t in tickets if t["assignee"] == assignee]
    
    return json.dumps({
        "success": True,
        "count": len(tickets),
        "tickets": tickets
    })


def zendesk_search_tickets(query: str) -> str:
    """Search Zendesk tickets by subject or description
    
    Args:
        query: Search term to look for in subject and description
    
    Returns:
        JSON string with matching tickets
    """
    query_lower = query.lower()
    
    matching = []
    for ticket in _mock_zendesk_tickets.values():
        if (query_lower in ticket["subject"].lower() or 
            query_lower in ticket["description"].lower() or
            query_lower in (ticket.get("requester_email") or "").lower()):
            matching.append(ticket)
    
    return json.dumps({
        "success": True,
        "query": query,
        "count": len(matching),
        "tickets": matching
    })


def zendesk_close_ticket(ticket_id: str, resolution_comment: str = None) -> str:
    """Close a Zendesk ticket
    
    Args:
        ticket_id: The ticket ID to close
        resolution_comment: Optional final comment explaining the resolution
    
    Returns:
        JSON string with the closed ticket
    """
    ticket = _mock_zendesk_tickets.get(ticket_id)
    
    if not ticket:
        return json.dumps({
            "success": False,
            "error": f"Ticket {ticket_id} not found"
        })
    
    now = datetime.utcnow().isoformat() + "Z"
    
    if resolution_comment:
        ticket["comments"].append({
            "author": "system",
            "body": f"[Resolution] {resolution_comment}",
            "created_at": now
        })
    
    ticket["status"] = "closed"
    ticket["updated_at"] = now
    
    return json.dumps({
        "success": True,
        "ticket": ticket
    })
