"""Slack function implementations"""
import json
import time

# In-memory mock of Slack workspaces
# Users
_mock_users = {
    "U001": {"id": "U001", "name": "alice", "real_name": "Alice Johnson", "email": "alice@company.com", "is_admin": True},
    "U002": {"id": "U002", "name": "bob", "real_name": "Bob Smith", "email": "bob@company.com", "is_admin": False},
    "U003": {"id": "U003", "name": "charlie", "real_name": "Charlie Brown", "email": "charlie@company.com", "is_admin": False},
    "U004": {"id": "U004", "name": "diana", "real_name": "Diana Prince", "email": "diana@company.com", "is_admin": False},
}

# Channels
_mock_channels = {
    "C001": {
        "id": "C001",
        "name": "general",
        "is_private": False,
        "topic": "Company-wide announcements",
        "members": ["U001", "U002", "U003", "U004"],
        "created": 1609459200
    },
    "C002": {
        "id": "C002",
        "name": "engineering",
        "is_private": False,
        "topic": "Engineering discussions",
        "members": ["U001", "U002", "U003"],
        "created": 1609545600
    },
    "C003": {
        "id": "C003",
        "name": "leadership",
        "is_private": True,
        "topic": "Leadership team private channel",
        "members": ["U001"],
        "created": 1609632000
    }
}

# Messages
_mock_messages = {
    "C001": [
        {"ts": "1609459201.000100", "user": "U001", "text": "Welcome to the team!"},
        {"ts": "1609459202.000200", "user": "U002", "text": "Thanks! Happy to be here."},
    ],
    "C002": [
        {"ts": "1609545601.000100", "user": "U001", "text": "Let's discuss the new feature."},
        {"ts": "1609545602.000200", "user": "U003", "text": "I have some ideas about the API design."},
    ],
    "C003": []
}

_channel_counter = 4
_user_counter = 5


def slack_create_channel(name: str, is_private: bool) -> str:
    """Create a new Slack channel"""
    global _channel_counter
    
    # Check if channel name already exists
    for channel in _mock_channels.values():
        if channel["name"] == name:
            return json.dumps({"success": False, "error": "name_taken"})
    
    channel_id = f"C{_channel_counter:03d}"
    _channel_counter += 1
    
    _mock_channels[channel_id] = {
        "id": channel_id,
        "name": name,
        "is_private": is_private,
        "topic": "",
        "members": [],
        "created": int(time.time())
    }
    _mock_messages[channel_id] = []
    
    return json.dumps({
        "success": True,
        "channel": _mock_channels[channel_id]
    })


def slack_list_channels() -> str:
    """List all Slack channels"""
    channels = [
        {
            "id": ch["id"],
            "name": ch["name"],
            "is_private": ch["is_private"],
            "num_members": len(ch["members"])
        }
        for ch in _mock_channels.values()
    ]
    return json.dumps({"success": True, "channels": channels})


def slack_get_channel_info(channel_id: str) -> str:
    """Get detailed information about a Slack channel"""
    if channel_id not in _mock_channels:
        return json.dumps({"success": False, "error": "channel_not_found"})
    
    return json.dumps({
        "success": True,
        "channel": _mock_channels[channel_id]
    })


def slack_invite_to_channel(channel_id: str, user_ids: list) -> str:
    """Invite users to a Slack channel"""
    if channel_id not in _mock_channels:
        return json.dumps({"success": False, "error": "channel_not_found"})
    
    channel = _mock_channels[channel_id]
    invited = []
    already_in = []
    not_found = []
    
    for user_id in user_ids:
        if user_id not in _mock_users:
            not_found.append(user_id)
        elif user_id in channel["members"]:
            already_in.append(user_id)
        else:
            channel["members"].append(user_id)
            invited.append(user_id)
    
    return json.dumps({
        "success": True,
        "invited": invited,
        "already_in_channel": already_in,
        "not_found": not_found
    })


def slack_remove_user_from_channel(channel_id: str, user_id: str) -> str:
    """Remove a user from a Slack channel"""
    if channel_id not in _mock_channels:
        return json.dumps({"success": False, "error": "channel_not_found"})
    
    channel = _mock_channels[channel_id]
    if user_id in channel["members"]:
        channel["members"].remove(user_id)
        return json.dumps({"success": True})
    else:
        return json.dumps({"success": False, "error": "not_in_channel"})


def slack_send_message(channel_id: str, text: str, blocks: dict = None) -> str:
    """Send a message to a Slack channel"""
    if channel_id not in _mock_channels:
        return json.dumps({"success": False, "error": "channel_not_found"})
    
    timestamp = f"{time.time():.6f}"
    message = {
        "ts": timestamp,
        "user": "U001",  # Default to first user
        "text": text
    }
    
    if blocks:
        message["blocks"] = blocks
    
    _mock_messages[channel_id].append(message)
    
    return json.dumps({
        "success": True,
        "channel": channel_id,
        "ts": timestamp,
        "message": message
    })


def slack_list_messages(channel_id: str, limit: int = 10) -> str:
    """List recent messages in a Slack channel"""
    if channel_id not in _mock_channels:
        return json.dumps({"success": False, "error": "channel_not_found"})
    
    messages = _mock_messages[channel_id][-limit:]
    
    return json.dumps({
        "success": True,
        "messages": messages,
        "has_more": len(_mock_messages[channel_id]) > limit
    })


def slack_list_users() -> str:
    """List all users in the Slack workspace"""
    users = list(_mock_users.values())
    return json.dumps({
        "success": True,
        "members": users
    })


def slack_get_user_info(user_id: str) -> str:
    """Get detailed information about a Slack user"""
    if user_id not in _mock_users:
        return json.dumps({"success": False, "error": "user_not_found"})
    
    return json.dumps({
        "success": True,
        "user": _mock_users[user_id]
    })


def slack_invite_user(email: str, name: str, channels: list = None) -> str:
    """Invite a user to the Slack workspace
    
    In this mock, the user is immediately created and added to specified channels.
    
    Args:
        email: User's email address
        name: User's display name
        channels: Optional list of channel IDs to add the user to
    
    Returns:
        JSON with success status and user details
    """
    global _user_counter
    
    # Check if user with this email already exists
    for user in _mock_users.values():
        if user.get("email") == email:
            return json.dumps({
                "success": True,
                "already_invited": True,
                "message": f"User with email {email} already exists in workspace",
                "user": user
            })
    
    # Create new user
    user_id = f"U{_user_counter:03d}"
    _user_counter += 1
    
    # Generate username from email
    username = email.split("@")[0].lower().replace(".", "_")
    
    new_user = {
        "id": user_id,
        "name": username,
        "real_name": name,
        "email": email,
        "is_admin": False
    }
    
    _mock_users[user_id] = new_user
    
    # Add to specified channels
    channels_joined = []
    channels_not_found = []
    
    if channels:
        for channel_id in channels:
            if channel_id in _mock_channels:
                if user_id not in _mock_channels[channel_id]["members"]:
                    _mock_channels[channel_id]["members"].append(user_id)
                channels_joined.append({
                    "id": channel_id,
                    "name": _mock_channels[channel_id]["name"]
                })
            else:
                channels_not_found.append(channel_id)
    
    return json.dumps({
        "success": True,
        "invited": True,
        "user": new_user,
        "channels_joined": channels_joined,
        "channels_not_found": channels_not_found,
        "message": f"Invited {name} ({email}) to workspace"
    })
