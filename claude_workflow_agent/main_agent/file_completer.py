"""
File and directory completer for @ mentions
"""

import os
from pathlib import Path
from typing import List, Iterable
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document


class FileCompleter(Completer):
    """
    Autocomplete files and directories when user types @
    """
    
    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir).resolve()
    
    def get_completions(self, document: Document, complete_event) -> Iterable[Completion]:
        """
        Generate completions for the current input.
        
        Triggers when user types @ followed by a path.
        """
        text = document.text_before_cursor
        
        # Find all @ mentions in the text
        at_positions = [i for i, char in enumerate(text) if char == '@']
        
        if not at_positions:
            return
        
        # Get the last @ mention
        last_at = at_positions[-1]
        after_at = text[last_at + 1:]
        
        # Check if there's a space after @ (means this @ is done)
        if ' ' in after_at and after_at.index(' ') < len(after_at) - 1:
            return
        
        # Get the path being typed after @
        path_part = after_at.strip()
        
        # Generate completions
        completions = self._get_path_completions(path_part)
        
        for completion in completions:
            # Calculate start position (where @ starts)
            start_position = -(len(path_part))
            
            yield Completion(
                text=completion['text'],
                start_position=start_position,
                display=completion['display'],
                display_meta=completion['meta']
            )
    
    def _get_path_completions(self, partial_path: str) -> List[dict]:
        """
        Get file/directory completions for a partial path.
        
        Args:
            partial_path: The path typed after @
        
        Returns:
            List of completion dicts
        """
        completions = []
        
        # Determine the directory to search in
        if partial_path:
            # If path contains /, split into dir and prefix
            if '/' in partial_path:
                dir_part, prefix = partial_path.rsplit('/', 1)
                search_dir = self.base_dir / dir_part
            else:
                search_dir = self.base_dir
                prefix = partial_path
        else:
            search_dir = self.base_dir
            prefix = ""
        
        # Check if directory exists
        if not search_dir.exists() or not search_dir.is_dir():
            return completions
        
        # List files and directories
        try:
            items = sorted(search_dir.iterdir())
            
            for item in items:
                item_name = item.name
                
                # Skip hidden files unless prefix starts with .
                if item_name.startswith('.') and not prefix.startswith('.'):
                    continue
                
                # Check if item matches prefix
                if not item_name.lower().startswith(prefix.lower()):
                    continue
                
                # Build relative path from base_dir
                try:
                    rel_path = item.relative_to(self.base_dir)
                except ValueError:
                    # If item is not relative to base_dir, use absolute path
                    rel_path = item
                
                # Determine display name and meta
                if item.is_dir():
                    display = f"📁 {item_name}/"
                    text = str(rel_path) + "/"
                    meta = "directory"
                else:
                    # Show file extension
                    ext = item.suffix
                    if ext:
                        icon = self._get_file_icon(ext)
                        display = f"{icon} {item_name}"
                    else:
                        display = f"📄 {item_name}"
                    text = str(rel_path)
                    meta = f"file ({ext})" if ext else "file"
                
                completions.append({
                    'text': text,
                    'display': display,
                    'meta': meta
                })
        
        except PermissionError:
            pass  # Skip directories we can't access
        
        return completions
    
    def _get_file_icon(self, ext: str) -> str:
        """Get emoji icon for file extension"""
        icons = {
            '.md': '📝',
            '.txt': '📄',
            '.py': '🐍',
            '.json': '📋',
            '.yaml': '⚙️',
            '.yml': '⚙️',
            '.sh': '🔧',
            '.log': '📊',
        }
        return icons.get(ext.lower(), '📄')


def parse_file_mentions(text: str, base_dir: str = ".") -> tuple[str, List[tuple[str, str]]]:
    """
    Parse @ file mentions from text and read their contents.
    
    Args:
        text: Input text with @file mentions
        base_dir: Base directory for resolving paths
    
    Returns:
        Tuple of (expanded_text, [(original_mention, file_content)])
    """
    base_path = Path(base_dir).resolve()
    mentions = []
    expanded_text = text
    
    # Find all @ mentions
    import re
    # Match @path/to/file or @file.txt (stops at space or end of string)
    pattern = r'@([^\s]+)'
    
    for match in re.finditer(pattern, text):
        mention = match.group(0)  # Full match including @
        file_path = match.group(1)  # Path without @
        
        # Resolve path
        full_path = base_path / file_path
        
        if full_path.exists() and full_path.is_file():
            try:
                with open(full_path, 'r') as f:
                    content = f.read()
                
                # Replace @mention with file content in text
                replacement = f"\n\n--- Content from {file_path} ---\n{content}\n--- End of {file_path} ---\n\n"
                expanded_text = expanded_text.replace(mention, replacement)
                
                mentions.append((mention, content))
            except Exception as e:
                # If can't read, leave the mention as-is
                print(f"⚠️  Could not read {file_path}: {e}")
        else:
            # File doesn't exist, leave mention as-is
            if not full_path.exists():
                print(f"⚠️  File not found: {file_path}")
    
    return expanded_text, mentions
