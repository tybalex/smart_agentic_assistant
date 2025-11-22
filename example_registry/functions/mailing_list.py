


import json
mailing_list = set()

def get_mailing_list() -> str:
    """Get the mailing list"""
    return json.dumps(list(mailing_list)) # convert set to list for JSON serialization

def add_to_mailing_list(email: str) -> str:
    """Add an email to the mailing list"""
    mailing_list.add(email)
    return f"Added {email} to the mailing list"

def remove_from_mailing_list(email: str) -> str:
    """Remove an email from the mailing list"""
    mailing_list.discard(email)
    return f"Removed {email} from the mailing list"