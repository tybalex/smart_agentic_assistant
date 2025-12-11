"""Member Desk invitation and management functions"""
import json
import time

# In-memory mock of Member Desk invitations
# Structure: [{email, name, role, invited_at, status}]
_member_desk_invitations = []

def member_desk_invite(email: str, name: str, role: str) -> str:
    """Invite a contact to CNCF Member Desk (idempotent operation).
    
    Args:
        email: Contact's email address
        name: Contact's full name  
        role: Contact's role (Primary, Technical, Marketing)
    
    Returns:
        JSON string with success status, invitation details including invitation_link,
        and confirmation message. If already invited, returns already_invited flag
    """
    # Check if already invited
    for invitation in _member_desk_invitations:
        if invitation["email"] == email:
            return json.dumps({
                "success": True,
                "already_invited": True,
                "message": f"{email} was already invited to Member Desk on {invitation['invited_at']}"
            })
    
    # Create invitation
    invitation = {
        "email": email,
        "name": name,
        "role": role,
        "invited_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "pending",
        "invitation_link": f"https://memberdesk.cncf.io/invite/{hash(email) % 1000000}"
    }
    
    _member_desk_invitations.append(invitation)
    
    return json.dumps({
        "success": True,
        "invited": True,
        "email": email,
        "name": name,
        "role": role,
        "invitation_link": invitation["invitation_link"],
        "message": f"Invited {name} ({email}) as {role} contact to Member Desk"
    })

def member_desk_list_invitations() -> str:
    """List all Member Desk invitations.
    
    Returns:
        JSON string with success status, invitations list (each with email, name, role,
        invited_at, status, invitation_link), and total count
    """
    return json.dumps({
        "success": True,
        "invitations": _member_desk_invitations,
        "total": len(_member_desk_invitations)
    })

def member_desk_accept_invitation(email: str) -> str:
    """Mark a Member Desk invitation as accepted (for testing purposes).
    
    Args:
        email: Email address of the invitation to accept
    
    Returns:
        JSON string with success status (false if invitation not found) and confirmation message
    """
    for invitation in _member_desk_invitations:
        if invitation["email"] == email:
            invitation["status"] = "accepted"
            invitation["accepted_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            return json.dumps({
                "success": True,
                "message": f"Invitation for {email} marked as accepted"
            })
    
    return json.dumps({
        "success": False,
        "error": "Invitation not found"
    })

def member_desk_get_invitation_status(email: str) -> str:
    """Get the status of a Member Desk invitation.
    
    Args:
        email: Email address of the invitation to check
    
    Returns:
        JSON string with success status (false if not found) and full invitation details
        including email, name, role, invited_at, status, and invitation_link
    """
    for invitation in _member_desk_invitations:
        if invitation["email"] == email:
            return json.dumps({
                "success": True,
                "invitation": invitation
            })
    
    return json.dumps({
        "success": False,
        "error": "Invitation not found"
    })

