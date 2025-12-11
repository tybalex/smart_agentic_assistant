"""Mailing list management functions"""
import json

# In-memory mock of multiple mailing lists
# Structure: {list_name: set of emails}
_mailing_lists = {
    "member": set(),
    "toc": set(),
    "marketing": set(),
    "chinese_member": set(),
    "end_user": set(),
}

def get_mailing_list(list_name: str) -> str:
    """Get the members of a specific mailing list.
    
    Args:
        list_name: Name of the mailing list (e.g., 'member', 'toc', 'marketing', 'chinese_member', 'end_user')
    
    Returns:
        JSON string with success status, list_name, members (list of email addresses), and count
    """
    if list_name not in _mailing_lists:
        return json.dumps({"success": False, "error": f"Mailing list '{list_name}' not found"})
    
    return json.dumps({
        "success": True,
        "list_name": list_name,
        "members": list(_mailing_lists[list_name]),
        "count": len(_mailing_lists[list_name])
    })

def add_to_mailing_list(list_name: str, email: str) -> str:
    """Add an email to a specific mailing list (idempotent operation).
    
    Args:
        list_name: Name of the mailing list. Creates the list if it doesn't exist
        email: Email address to add to the list
    
    Returns:
        JSON string with success status, confirmation message, and action taken
        ('added' for new email or 'already_exists' if email was already in list)
    """
    if list_name not in _mailing_lists:
        # Create new list if it doesn't exist
        _mailing_lists[list_name] = set()
    
    already_exists = email in _mailing_lists[list_name]
    _mailing_lists[list_name].add(email)
    
    if already_exists:
        return json.dumps({
            "success": True,
            "message": f"Email {email} was already in '{list_name}' mailing list",
            "action": "already_exists"
        })
    return json.dumps({
        "success": True,
        "message": f"Added {email} to '{list_name}' mailing list",
        "action": "added"
    })

def remove_from_mailing_list(list_name: str, email: str) -> str:
    """Remove an email from a specific mailing list.
    
    Args:
        list_name: Name of the mailing list
        email: Email address to remove from the list
    
    Returns:
        JSON string with success status, confirmation message, and action taken
        ('removed' if email was found and removed, or 'not_found' if email wasn't in list)
    """
    if list_name not in _mailing_lists:
        return json.dumps({"success": False, "error": f"Mailing list '{list_name}' not found"})
    
    if email not in _mailing_lists[list_name]:
        return json.dumps({
            "success": True,
            "message": f"Email {email} was not in '{list_name}' mailing list",
            "action": "not_found"
        })
    
    _mailing_lists[list_name].discard(email)
    return json.dumps({
        "success": True,
        "message": f"Removed {email} from '{list_name}' mailing list",
        "action": "removed"
    })

def list_all_mailing_lists() -> str:
    """List all available mailing lists and their member counts.
    
    Returns:
        JSON string with success status, list of mailing_lists (each with name and member_count),
        and total count of lists
    """
    lists_info = [
        {
            "name": list_name,
            "member_count": len(members)
        }
        for list_name, members in _mailing_lists.items()
    ]
    
    return json.dumps({
        "success": True,
        "mailing_lists": lists_info,
        "total": len(_mailing_lists)
    })

def create_mailing_list(list_name: str) -> str:
    """Create a new empty mailing list.
    
    Args:
        list_name: Name for the new mailing list
    
    Returns:
        JSON string with success status (false if list already exists) and confirmation message
    """
    if list_name in _mailing_lists:
        return json.dumps({
            "success": False,
            "error": f"Mailing list '{list_name}' already exists"
        })
    
    _mailing_lists[list_name] = set()
    return json.dumps({
        "success": True,
        "message": f"Created mailing list '{list_name}'"
    })
