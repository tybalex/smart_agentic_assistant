#!/usr/bin/env python3
"""
Workflow Agent CLI Entry Point
Run: python main_cli.py
"""

import sys
import argparse
from main_agent.cli import WorkflowCLI
import asyncio

def main():
    parser = argparse.ArgumentParser(
        description="Claude Workflow Agent - Main Agent CLI"
    )
    parser.add_argument(
        '--dev',
        action='store_true',
        help='Enable dev mode (shows tool calls and results)'
    )
    
    args = parser.parse_args()
    
    # Run CLI with dev mode setting
    cli = WorkflowCLI(dev_mode=args.dev)
    asyncio.run(cli.run())

if __name__ == "__main__":
    main()
