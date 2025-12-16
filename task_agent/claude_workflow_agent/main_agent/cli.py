#!/usr/bin/env python3
"""
Main Agent CLI - Interactive workflow development interface
"""

import asyncio
import sys
import argparse
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML

from .agent import MainAgent
from .file_completer import FileCompleter, parse_file_mentions


class WorkflowCLI:
    """Interactive CLI for Main Agent"""
    
    def __init__(self, dev_mode: bool = False):
        self.agent = MainAgent(dev_mode=dev_mode)
        self.running = True
        self.base_dir = Path.cwd()
        self.dev_mode = dev_mode
        
        # Setup prompt with file completion
        self.prompt_session = PromptSession(
            completer=FileCompleter(base_dir=str(self.base_dir)),
            complete_while_typing=True
        )
        
        # Style for prompt
        self.prompt_style = Style.from_dict({
            'prompt': '#00aa00 bold',
        })
        
        # ANSI color codes
        self.COLOR_TOOL = '\033[96m'      # Cyan for tool calls
        self.COLOR_RESULT = '\033[93m'    # Yellow for results
        self.COLOR_SUCCESS = '\033[92m'   # Green for success
        self.COLOR_ERROR = '\033[91m'     # Red for errors
        self.COLOR_RESET = '\033[0m'      # Reset
        self.COLOR_BOLD = '\033[1m'       # Bold
    
    def print_welcome(self):
        """Print welcome message"""
        print("╔" + "═" * 78 + "╗")
        print("║" + " " * 78 + "║")
        print("║" + " " * 20 + "🤖 Claude Workflow Agent" + " " * 33 + "║")
        print("║" + " " * 25 + "Main Agent" + " " * 42 + "║")
        print("║" + " " * 78 + "║")
        print("╚" + "═" * 78 + "╝")
        print()
        print("I help you create and improve executable workflows.")
        print("Similar to Claude Code, but for workflows instead of code!")
        print()
        if self.dev_mode:
            print(f"{self.COLOR_BOLD}{self.COLOR_TOOL}🔧 DEV MODE ENABLED{self.COLOR_RESET} - Tool calls and results will be shown")
            print()
        print("📝 Tips:")
        print("  - Tell me what workflow you want to create")
        print("  - Use @ to reference files: 'read from @input/workflow.txt'")
        print("  - I'll write it, test it, and improve it based on execution results")
        print("  - Type 'quit' or 'exit' to leave")
        print("  - Type 'status' to see current session info")
        print()
    
    async def run(self):
        """Run the interactive CLI"""
        self.print_welcome()
        
        # Start session with default name (can be changed later)
        self.agent.start_session("workflow")
        
        print("💬 Tell me what workflow you want to create, or try:")
        print("   • 'Create a workflow to onboard new employees'")
        print("   • 'Read from @input/CNCF_workflow.txt and create that'")
        print("   • 'help' for more examples")
        print()
        
        # Interactive loop
        while self.running:
            try:
                # Get user input with autocomplete
                user_input = await self.prompt_session.prompt_async(
                    HTML('<ansiyellow>></ansiyellow> '),
                    style=self.prompt_style
                )
                user_input = user_input.strip()
                
                if not user_input:
                    continue
                
                # Handle special commands
                if user_input.lower() in ['quit', 'exit', 'q']:
                    self.running = False
                    print("\nGoodbye! 👋")
                    break
                
                if user_input.lower() == 'status':
                    print("\n" + "─" * 80)
                    print("SESSION STATUS")
                    print("─" * 80)
                    print(self.agent.get_session_summary())
                    print("─" * 80)
                    continue
                
                if user_input.lower() in ['help', '?']:
                    self.print_help()
                    continue
                
                # Parse @ file mentions and expand them
                expanded_input, mentions = parse_file_mentions(user_input, base_dir=str(self.base_dir))
                
                # Show what files were included
                if mentions:
                    print()
                    print("📎 Included files:")
                    for mention, _ in mentions:
                        print(f"   {mention}")
                    print()
                
                # Process with agent
                print()
                print("💭 Thinking...")
                print()
                
                response = await self.agent.chat(expanded_input)
                
                # Print response
                print("─" * 80)
                print(response)
                print("─" * 80)
                
            except KeyboardInterrupt:
                print("\n\n⚠️  Interrupted. Type 'quit' to exit properly.")
                continue
            except Exception as e:
                print(f"\n❌ Error: {e}")
                import traceback
                traceback.print_exc()
                continue
    
    def print_help(self):
        """Print help message"""
        print("\n" + "─" * 80)
        print("HELP - Just chat naturally!")
        print("─" * 80)
        print()
        print("🎯 Getting Started:")
        print("  1. Describe what you want: 'Create a workflow to...'")
        print("  2. Or load from file: 'Read @input/CNCF_workflow.txt'")
        print("  3. I'll write the workflow, test it, and improve it!")
        print()
        print("📎 File References (@-mentions):")
        print("  • Type @ to see file/folder autocomplete")
        print("  • Example: 'Use @input/requirements.txt'")
        print("  • File content is automatically included")
        print()
        print("💬 Conversation Examples:")
        print("  • 'Create a workflow to onboard new employees'")
        print("  • 'Add a step to send welcome email'")
        print("  • 'Run the workflow and test it'")
        print("  • 'Fix the error from the last run'")
        print()
        print("📋 Commands:")
        print("  status  - Show session info (iterations, executions)")
        print("  help/?  - Show this message")
        print("  quit    - Exit")
        print("─" * 80)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Claude Workflow Agent - Main Agent CLI"
    )
    parser.add_argument(
        '--dev',
        action='store_true',
        help='Enable dev mode (shows tool calls and results)'
    )
    
    args = parser.parse_args()
    
    cli = WorkflowCLI(dev_mode=args.dev)
    asyncio.run(cli.run())


if __name__ == "__main__":
    main()
