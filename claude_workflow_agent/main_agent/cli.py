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
                
                # Handle response based on type
                await self._handle_response(response)
                
            except KeyboardInterrupt:
                print("\n\n⚠️  Interrupted. Type 'quit' to exit properly.")
                continue
            except Exception as e:
                print(f"\n❌ Error: {e}")
                import traceback
                traceback.print_exc()
                continue
    
    async def _handle_response(self, response: dict):
        """Handle agent response - either text or tool calls"""
        if response["type"] == "text":
            # Simple text response
            print("─" * 80)
            print(response["content"])
            print("─" * 80)
        
        elif response["type"] == "tool_calls":
            # Tool calls need approval
            await self._handle_tool_approval(response)
    
    async def _handle_tool_approval(self, response: dict):
        """Handle tool call approval workflow"""
        # Show agent's reasoning/plan
        if response["content"]:
            print()
            print("─" * 80)
            print(f"{self.COLOR_BOLD}🎯 Agent's Plan:{self.COLOR_RESET}")
            print(response["content"])
            print("─" * 80)
        
        # Show tool calls
        tool_calls = response["tool_calls"]
        print()
        print(f"{self.COLOR_BOLD}{self.COLOR_TOOL}🔧 Proposed Tool Calls ({len(tool_calls)} total):{self.COLOR_RESET}")
        print()
        
        for idx, tool_call in enumerate(tool_calls, 1):
            print(f"{self.COLOR_TOOL}{idx}. {tool_call['tool']}{self.COLOR_RESET}")
            if tool_call.get('arguments'):
                for key, value in tool_call['arguments'].items():
                    value_str = str(value)
                    if len(value_str) > 100:
                        value_str = value_str[:100] + "..."
                    print(f"   {key}: {value_str}")
            print()
        
        # Get user approval
        print("─" * 80)
        print(f"{self.COLOR_BOLD}Approve these tool calls?{self.COLOR_RESET}")
        print("  • Enter 'yes' or 'y' to approve all")
        print("  • Enter 'no' or 'n' to reject all (with optional feedback)")
        print("  • Enter specific numbers to approve only those (e.g., '1,3')")
        print()
        
        approval_input = await self.prompt_session.prompt_async(
            HTML('<ansiyellow>Approve?</ansiyellow> '),
            style=self.prompt_style
        )
        approval_input = approval_input.strip().lower()
        
        approved_tools = []
        rejected_tools = []
        rejection_feedback = None
        
        if approval_input in ['yes', 'y', '']:
            # Approve all
            approved_tools = tool_calls
        
        elif approval_input in ['no', 'n']:
            # Reject all - ask for feedback
            print()
            print("Why are you rejecting? (This helps the agent understand):")
            feedback_input = await self.prompt_session.prompt_async(
                HTML('<ansiyellow>Feedback:</ansiyellow> '),
                style=self.prompt_style
            )
            rejection_feedback = feedback_input.strip() or "User rejected without specific feedback"
            
            # Mark all as rejected with feedback
            for tool_call in tool_calls:
                rejected_tool = tool_call.copy()
                rejected_tool["feedback"] = rejection_feedback
                rejected_tools.append(rejected_tool)
        
        else:
            # Partial approval - parse numbers
            try:
                # Parse comma-separated numbers
                approved_indices = set()
                for part in approval_input.split(','):
                    part = part.strip()
                    if part.isdigit():
                        approved_indices.add(int(part))
                
                # Split into approved/rejected
                for idx, tool_call in enumerate(tool_calls, 1):
                    if idx in approved_indices:
                        approved_tools.append(tool_call)
                    else:
                        rejected_tools.append(tool_call)
                
                # Get feedback for rejected tools if any
                if rejected_tools:
                    print()
                    print(f"Why reject the other {len(rejected_tools)} tool(s)?")
                    feedback_input = await self.prompt_session.prompt_async(
                        HTML('<ansiyellow>Feedback:</ansiyellow> '),
                        style=self.prompt_style
                    )
                    rejection_feedback = feedback_input.strip() or "User rejected without specific feedback"
                    
                    # Add feedback to rejected tools
                    for tool in rejected_tools:
                        tool["feedback"] = rejection_feedback
            
            except Exception as e:
                print(f"\n{self.COLOR_ERROR}Invalid input. Please enter 'yes', 'no', or numbers like '1,2,3'{self.COLOR_RESET}")
                print("Treating as rejection...")
                rejection_feedback = "Invalid approval input"
                for tool_call in tool_calls:
                    rejected_tool = tool_call.copy()
                    rejected_tool["feedback"] = rejection_feedback
                    rejected_tools.append(rejected_tool)
        
        # Show execution message for approved tools
        if approved_tools:
            print()
            print(f"{self.COLOR_SUCCESS}✓ Executing {len(approved_tools)} approved tool(s)...{self.COLOR_RESET}")
            print()
        
        # Continue with agent
        next_response = await self.agent.continue_with_tool_results(
            approved_tools=approved_tools,
            rejected_tools=rejected_tools
        )
        
        # Recursively handle the next response (might be more tool calls)
        await self._handle_response(next_response)
    
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
        print("🔧 Tool Approval:")
        print("  • Agent will propose tool calls before executing")
        print("  • You can approve all, reject all, or select specific ones")
        print("  • Provide feedback when rejecting to guide the agent")
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
