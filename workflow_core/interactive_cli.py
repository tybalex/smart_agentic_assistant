"""
Interactive CLI for workflow development

A simple REPL where users chat with an agentic workflow assistant.
The agent has tools and autonomously decides how to accomplish tasks.
"""

import sys
from pathlib import Path
import os

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.agent import WorkflowAgent


def print_header():
    print("\n" + "=" * 70)
    print("🤖 Smart Workflow - Agentic CLI")
    print("=" * 70)
    print("\nJust chat naturally! The agent will use tools automatically.")
    print("\nExamples:")
    print("  • Create a workflow that fetches user data and sends emails")
    print("  • Add error handling to the API call")
    print("  • Test the workflow")
    print("  • Save it as customer_workflow.yaml")
    print("\nCommands:")
    print("  /reset  - Start a new conversation")
    print("  /quit   - Exit")
    print("=" * 70 + "\n")


def main():
    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n⚠️  ANTHROPIC_API_KEY not set!")
        print("Set it with: export ANTHROPIC_API_KEY=your-key-here")
        return
    
    # Create agent
    agent = WorkflowAgent(workspace_dir=".")
    
    print_header()
    
    while True:
        try:
            # Get user input
            user_input = input("\n🧑 You: ").strip()
            
            if not user_input:
                continue
            
            # Handle commands
            if user_input.lower() in ["/quit", "/exit", "quit", "exit"]:
                print("\n👋 Goodbye!")
                break
            
            elif user_input.lower() in ["/reset", "reset"]:
                agent.reset_conversation()
                print("🔄 Conversation reset. Starting fresh!")
                continue
            
            elif user_input.lower() in ["/help", "help"]:
                print_header()
                continue
            
            # Send to agent
            print("\n🤖 Agent: ", end="", flush=True)
            response = agent.chat(user_input)
            print(response)
        
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except EOFError:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("Continuing...")


if __name__ == "__main__":
    main()
