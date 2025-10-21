#!/usr/bin/env python3
"""
Interactive console chat using PydanticAI Agent with gpt-4o-mini
connected to your browser automation MCP server via stdio.
"""

import asyncio
from pathlib import Path
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.mcp import MCPServerStdio
from dotenv import load_dotenv
load_dotenv()

async def main():
    print("🚀 Starting Browser Automation Chat (gpt-4o-mini + MCP stdio)")
    print("Type 'exit' or 'quit' to end.\n")

    # 1️⃣ Setup MCP stdio server — launches your browser MCP as subprocess
    browser_server = MCPServerStdio(
        "uv",
        args=["run", "server.py"],
        timeout=10,
    )

    # 2️⃣ Configure the AI model (gpt-4o-mini)
    model = OpenAIChatModel("gpt-4o-mini")

    # 3️⃣ Create the PydanticAI agent
    agent = Agent(
        name="browser-agent",
        model=model,
        system_prompt=(
            "An AI assistant that automates browsers using Playwright "
            "via an MCP server connection. You can instruct it to open websites, "
            "fill forms, click buttons, or take screenshots."
        ),
        toolsets=[browser_server],
    )
    
    print("🤖 Thinking...")
    result = await agent.run("open the browser page: https://docs.crawl4ai.com/ , and navigate through the documentation to find information about web scraping. Summarize the key points you find there.")
    print(f"🤖 Agent: {result.output}\n")
    # 4️⃣ Run chat with persistent conversation
    # async with agent:
    #     conversation = agent.create_conversation()
    #     while True:
    #         try:
    #             user_input = input("🧍 You: ").strip()
    #         except (EOFError, KeyboardInterrupt):
    #             print("\n👋 Exiting…")
    #             break

    #         if not user_input or user_input.lower() in {"exit", "quit"}:
    #             break

    #         print("🤖 Thinking...")
    #         try:
    #             response = await conversation.run(user_input)
    #             print(f"🤖 Agent: {response.output_text}\n")
    #         except Exception as e:
    #             print(f"❌ Error: {e}\n")

    print("🧹 MCP connection closed.")


if __name__ == "__main__":
    asyncio.run(main())
