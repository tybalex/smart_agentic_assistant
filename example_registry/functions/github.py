"""GitHub function implementations"""
import json
import hashlib
import time

# In-memory mock of GitHub repositories
_mock_repos = {
    "myorg/main-app": {
        "owner": "myorg",
        "name": "main-app",
        "full_name": "myorg/main-app",
        "default_branch": "main",
        "description": "Main application repository"
    },
    "myorg/docs": {
        "owner": "myorg",
        "name": "docs",
        "full_name": "myorg/docs",
        "default_branch": "main",
        "description": "Documentation repository"
    }
}

# Branches: {repo_full_name: {branch_name: {sha, ref, ...}}}
_mock_branches = {
    "myorg/main-app": {
        "main": {
            "name": "main",
            "commit": {
                "sha": "abc123def456",
                "message": "Initial commit",
                "author": {"name": "Admin", "email": "admin@example.com"},
                "date": "2024-01-01T00:00:00Z"
            },
            "protected": True
        },
        "develop": {
            "name": "develop",
            "commit": {
                "sha": "def456abc789",
                "message": "Development branch",
                "author": {"name": "Admin", "email": "admin@example.com"},
                "date": "2024-01-02T00:00:00Z"
            },
            "protected": False
        }
    },
    "myorg/docs": {
        "main": {
            "name": "main",
            "commit": {
                "sha": "xyz789uvw012",
                "message": "Initial docs",
                "author": {"name": "Admin", "email": "admin@example.com"},
                "date": "2024-01-01T00:00:00Z"
            },
            "protected": True
        }
    }
}

# Files: {repo_full_name: {branch_name: {file_path: content}}}
_mock_files = {
    "myorg/main-app": {
        "main": {
            "README.md": "# Main App\nWelcome to the main application.",
            "members.json": json.dumps([{"name": "Alice", "role": "Admin"}], indent=2)
        },
        "develop": {
            "README.md": "# Main App\nWelcome to the main application.",
            "members.json": json.dumps([{"name": "Alice", "role": "Admin"}], indent=2)
        }
    },
    "myorg/docs": {
        "main": {
            "README.md": "# Documentation\nProject documentation.",
            "CONTRIBUTING.md": "# Contributing\nHow to contribute."
        }
    }
}

# Pull Requests: {repo_full_name: [pr_objects]}
_mock_prs = {
    "myorg/main-app": [
        {
            "number": 1,
            "state": "open",
            "title": "Add new feature",
            "head": "feature/new-feature",
            "base": "main",
            "body": "This PR adds a new feature",
            "author": "developer1",
            "created_at": "2024-11-01T10:00:00Z",
            "updated_at": "2024-11-01T10:00:00Z"
        }
    ],
    "myorg/docs": []
}

_pr_counter = 2


def _generate_sha(content: str) -> str:
    """Generate a SHA hash similar to Git"""
    return hashlib.sha1(content.encode()).hexdigest()[:12]


def github_create_branch(owner: str, repo: str, branch_name: str, base_sha: str) -> str:
    """Create a new branch in a GitHub repository"""
    repo_full_name = f"{owner}/{repo}"
    
    if repo_full_name not in _mock_repos:
        return json.dumps({"success": False, "error": "repository_not_found"})
    
    if repo_full_name not in _mock_branches:
        _mock_branches[repo_full_name] = {}
    
    if branch_name in _mock_branches[repo_full_name]:
        return json.dumps({"success": False, "error": "branch_already_exists"})
    
    # Find base branch by SHA or use default
    base_branch = None
    for branch_data in _mock_branches[repo_full_name].values():
        if branch_data["commit"]["sha"] == base_sha:
            base_branch = branch_data
            break
    
    if not base_branch:
        # Use main/master as default
        default = _mock_repos[repo_full_name]["default_branch"]
        if default in _mock_branches[repo_full_name]:
            base_branch = _mock_branches[repo_full_name][default]
        else:
            return json.dumps({"success": False, "error": "base_branch_not_found"})
    
    # Create new branch
    new_sha = _generate_sha(f"{branch_name}{time.time()}")
    _mock_branches[repo_full_name][branch_name] = {
        "name": branch_name,
        "commit": {
            "sha": new_sha,
            "message": base_branch["commit"]["message"],
            "author": {"name": "System", "email": "system@example.com"},
            "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        },
        "protected": False
    }
    
    # Copy files from base branch
    if repo_full_name in _mock_files:
        # Find source branch name
        source_branch = None
        for br_name, br_data in _mock_branches[repo_full_name].items():
            if br_data["commit"]["sha"] == base_sha:
                source_branch = br_name
                break
        
        if source_branch and source_branch in _mock_files[repo_full_name]:
            _mock_files[repo_full_name][branch_name] = _mock_files[repo_full_name][source_branch].copy()
        else:
            _mock_files[repo_full_name][branch_name] = {}
    
    return json.dumps({
        "success": True,
        "ref": f"refs/heads/{branch_name}",
        "sha": new_sha,
        "object": {
            "sha": new_sha,
            "type": "commit"
        }
    })


def github_commit_file(owner: str, repo: str, path: str, content: str, message: str, branch: str) -> str:
    """Commit a file to a GitHub repository"""
    repo_full_name = f"{owner}/{repo}"
    
    if repo_full_name not in _mock_repos:
        return json.dumps({"success": False, "error": "repository_not_found"})
    
    if repo_full_name not in _mock_branches or branch not in _mock_branches[repo_full_name]:
        return json.dumps({"success": False, "error": "branch_not_found"})
    
    # Initialize files storage if needed
    if repo_full_name not in _mock_files:
        _mock_files[repo_full_name] = {}
    if branch not in _mock_files[repo_full_name]:
        _mock_files[repo_full_name][branch] = {}
    
    # Commit the file
    _mock_files[repo_full_name][branch][path] = content
    
    # Update branch SHA
    new_sha = _generate_sha(f"{path}{content}{time.time()}")
    _mock_branches[repo_full_name][branch]["commit"] = {
        "sha": new_sha,
        "message": message,
        "author": {"name": "System", "email": "system@example.com"},
        "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    
    return json.dumps({
        "success": True,
        "content": {
            "name": path.split("/")[-1],
            "path": path,
            "sha": _generate_sha(content),
            "size": len(content)
        },
        "commit": {
            "sha": new_sha,
            "message": message,
            "author": {"name": "System", "email": "system@example.com"}
        }
    })


def github_create_pr(owner: str, repo: str, title: str, head: str, base: str, body: str) -> str:
    """Create a pull request in GitHub"""
    global _pr_counter
    
    repo_full_name = f"{owner}/{repo}"
    
    if repo_full_name not in _mock_repos:
        return json.dumps({"success": False, "error": "repository_not_found"})
    
    if repo_full_name not in _mock_branches:
        return json.dumps({"success": False, "error": "no_branches_found"})
    
    if head not in _mock_branches[repo_full_name]:
        return json.dumps({"success": False, "error": "head_branch_not_found"})
    
    if base not in _mock_branches[repo_full_name]:
        return json.dumps({"success": False, "error": "base_branch_not_found"})
    
    # Create PR
    pr_number = _pr_counter
    _pr_counter += 1
    
    pr = {
        "number": pr_number,
        "state": "open",
        "title": title,
        "head": head,
        "base": base,
        "body": body,
        "author": "system",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mergeable": True,
        "merged": False
    }
    
    if repo_full_name not in _mock_prs:
        _mock_prs[repo_full_name] = []
    
    _mock_prs[repo_full_name].append(pr)
    
    return json.dumps({
        "success": True,
        "number": pr_number,
        "state": "open",
        "title": title,
        "html_url": f"https://github.com/{repo_full_name}/pull/{pr_number}",
        "user": {"login": "system"},
        "head": {"ref": head, "sha": _mock_branches[repo_full_name][head]["commit"]["sha"]},
        "base": {"ref": base, "sha": _mock_branches[repo_full_name][base]["commit"]["sha"]},
        "body": body,
        "created_at": pr["created_at"],
        "updated_at": pr["updated_at"]
    })


def github_list_branches(owner: str, repo: str) -> str:
    """List all branches in a GitHub repository"""
    repo_full_name = f"{owner}/{repo}"
    
    if repo_full_name not in _mock_repos:
        return json.dumps({"success": False, "error": "repository_not_found"})
    
    branches = []
    if repo_full_name in _mock_branches:
        for branch_name, branch_data in _mock_branches[repo_full_name].items():
            branches.append({
                "name": branch_name,
                "commit": {
                    "sha": branch_data["commit"]["sha"],
                    "url": f"https://api.github.com/repos/{repo_full_name}/commits/{branch_data['commit']['sha']}"
                },
                "protected": branch_data.get("protected", False)
            })
    
    return json.dumps({"success": True, "branches": branches})


def github_list_prs(owner: str, repo: str, state: str = "open") -> str:
    """List pull requests in a GitHub repository"""
    repo_full_name = f"{owner}/{repo}"
    
    if repo_full_name not in _mock_repos:
        return json.dumps({"success": False, "error": "repository_not_found"})
    
    prs = []
    if repo_full_name in _mock_prs:
        for pr in _mock_prs[repo_full_name]:
            if state == "all" or pr["state"] == state:
                prs.append(pr)
    
    return json.dumps({"success": True, "pull_requests": prs, "total": len(prs)})


def github_get_file(owner: str, repo: str, path: str, branch: str) -> str:
    """Get file content from a GitHub repository"""
    repo_full_name = f"{owner}/{repo}"
    
    if repo_full_name not in _mock_repos:
        return json.dumps({"success": False, "error": "repository_not_found"})
    
    if repo_full_name not in _mock_branches or branch not in _mock_branches[repo_full_name]:
        return json.dumps({"success": False, "error": "branch_not_found"})
    
    if repo_full_name not in _mock_files or branch not in _mock_files[repo_full_name]:
        return json.dumps({"success": False, "error": "no_files_in_branch"})
    
    if path not in _mock_files[repo_full_name][branch]:
        return json.dumps({"success": False, "error": "file_not_found"})
    
    content = _mock_files[repo_full_name][branch][path]
    
    return json.dumps({
        "success": True,
        "name": path.split("/")[-1],
        "path": path,
        "sha": _generate_sha(content),
        "size": len(content),
        "content": content,
        "encoding": "utf-8"
    })


def github_merge_pr(owner: str, repo: str, pr_number: int, commit_message: str = None) -> str:
    """Merge a pull request"""
    repo_full_name = f"{owner}/{repo}"
    
    if repo_full_name not in _mock_repos:
        return json.dumps({"success": False, "error": "repository_not_found"})
    
    if repo_full_name not in _mock_prs:
        return json.dumps({"success": False, "error": "pull_request_not_found"})
    
    # Find the PR
    pr = None
    for p in _mock_prs[repo_full_name]:
        if p["number"] == pr_number:
            pr = p
            break
    
    if not pr:
        return json.dumps({"success": False, "error": "pull_request_not_found"})
    
    if pr["state"] != "open":
        return json.dumps({"success": False, "error": "pull_request_not_open"})
    
    # Merge the PR (update state)
    pr["state"] = "closed"
    pr["merged"] = True
    pr["merged_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    
    # Copy files from head to base branch
    if repo_full_name in _mock_files:
        head_branch = pr["head"]
        base_branch = pr["base"]
        
        if head_branch in _mock_files[repo_full_name] and base_branch in _mock_files[repo_full_name]:
            # Merge files
            _mock_files[repo_full_name][base_branch].update(_mock_files[repo_full_name][head_branch])
            
            # Update base branch SHA
            merge_sha = _generate_sha(f"merge-{pr_number}-{time.time()}")
            _mock_branches[repo_full_name][base_branch]["commit"]["sha"] = merge_sha
    
    return json.dumps({
        "success": True,
        "merged": True,
        "message": "Pull request successfully merged",
        "sha": _generate_sha(f"merge-{pr_number}")
    })
