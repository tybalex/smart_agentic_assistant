"""Member Desk invitation and management functions"""
import json
import time

# In-memory mock of Member Desk invitations
# Structure: [{email, name, role, invited_at, status}]
_member_desk_invitations = []

def member_desk_invite(email: str, name: str, role: str) -> str:
    """Invite a contact to CNCF Member Desk
    
    Args:
        email: Contact's email address
        name: Contact's full name
        role: Contact's role (Primary, Technical, Marketing)
    """
    # Check if already invited
    for invitation in _member_desk_invitations:
        if invitation["email"] == email:
            return json.dumps({
                "ok": True,
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
        "ok": True,
        "invited": True,
        "email": email,
        "name": name,
        "role": role,
        "invitation_link": invitation["invitation_link"],
        "message": f"Invited {name} ({email}) as {role} contact to Member Desk"
    })

def member_desk_list_invitations() -> str:
    """List all Member Desk invitations"""
    return json.dumps({
        "ok": True,
        "invitations": _member_desk_invitations,
        "total": len(_member_desk_invitations)
    })

def member_desk_accept_invitation(email: str) -> str:
    """Mark a Member Desk invitation as accepted (for testing)"""
    for invitation in _member_desk_invitations:
        if invitation["email"] == email:
            invitation["status"] = "accepted"
            invitation["accepted_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            return json.dumps({
                "ok": True,
                "message": f"Invitation for {email} marked as accepted"
            })
    
    return json.dumps({
        "ok": False,
        "error": "Invitation not found"
    })

def member_desk_get_invitation_status(email: str) -> str:
    """Get the status of a Member Desk invitation"""
    for invitation in _member_desk_invitations:
        if invitation["email"] == email:
            return json.dumps({
                "ok": True,
                "invitation": invitation
            })
    
    return json.dumps({
        "ok": False,
        "error": "Invitation not found"
    })

