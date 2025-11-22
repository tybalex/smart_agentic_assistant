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
    """Get the members of a specific mailing list"""
    if list_name not in _mailing_lists:
        return json.dumps({"ok": False, "error": f"Mailing list '{list_name}' not found"})
    
    return json.dumps({
        "ok": True,
        "list_name": list_name,
        "members": list(_mailing_lists[list_name])
    })

def add_to_mailing_list(list_name: str, email: str) -> str:
    """Add an email to a specific mailing list (idempotent)"""
    if list_name not in _mailing_lists:
        # Create new list if it doesn't exist
        _mailing_lists[list_name] = set()
    
    already_exists = email in _mailing_lists[list_name]
    _mailing_lists[list_name].add(email)
    
    if already_exists:
        return f"Email {email} was already in '{list_name}' mailing list"
    else:
        return f"Added {email} to '{list_name}' mailing list"

def remove_from_mailing_list(list_name: str, email: str) -> str:
    """Remove an email from a specific mailing list"""
    if list_name not in _mailing_lists:
        return json.dumps({"ok": False, "error": f"Mailing list '{list_name}' not found"})
    
    _mailing_lists[list_name].discard(email)
    return f"Removed {email} from '{list_name}' mailing list"

def list_all_mailing_lists() -> str:
    """List all available mailing lists and their member counts"""
    lists_info = [
        {
            "name": list_name,
            "member_count": len(members)
        }
        for list_name, members in _mailing_lists.items()
    ]
    
    return json.dumps({
        "ok": True,
        "mailing_lists": lists_info,
        "total": len(_mailing_lists)
    })

def create_mailing_list(list_name: str) -> str:
    """Create a new mailing list"""
    if list_name in _mailing_lists:
        return json.dumps({"ok": False, "error": f"Mailing list '{list_name}' already exists"})
    
    _mailing_lists[list_name] = set()
    return json.dumps({
        "ok": True,
        "message": f"Created mailing list '{list_name}'"
    })
