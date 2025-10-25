# Jarvis Voice Assistant

A modular voice-controlled assistant with an extensible tool system powered by LLM-based intelligent routing.

## Features

- 🎤 **Continuous listening** with automatic phrase segmentation
- 🗣️ **Speech-to-Text** using Whisper or PocketSphinx
- 🔊 **Text-to-Speech** with pyttsx3
- 🤖 **Intelligent tool routing** - LLM automatically selects the best tools
- ⚡ **Parallel execution** - runs multiple tools concurrently
- 🛠️ **Extensible tool system** - easily add new capabilities
- 🌐 **Web automation** and **multi-engine search**

## Quick Start

### Installation

```bash
# Clone repository
git clone <repo-url>
cd jarvis

# Install all dependencies
uv sync
```

### Configuration

Create a `.env` file in the project root:

```env
# OpenAI API Key (required for LLM-based routing and some tools)
OPENAI_API_KEY=sk-your-key-here

# Speech Recognition
LANGUAGE=en-US
USE_WHISPER=true
WHISPER_MODEL=tiny
PAUSE_THRESHOLD=0.6
PHRASE_TIME_LIMIT=12.0

# Text-to-Speech
TTS_RATE=170
TTS_VOLUME=1.0
TTS_VOICE_PREFERENCE=jamie

# Stop Words (exit assistant)
STOP_WORDS=stop,quit,exit

# Tools (comma-separated list)
ENABLED_TOOLS=["playwright_agent", "calculator", "datetime", "gmail", "search_tool"]
PLAYWRIGHT_HEADLESS=true
```

### Run

```bash
uv run main.py
```

Say any command, and Jarvis will intelligently select the appropriate tool(s) to help you!

## How It Works

Jarvis uses a sophisticated pipeline to process your voice commands:

```
1. Detect Voice → 2. Voice-to-Text → 3. Tool Processing → 4. Format Result → 5. Speak Result
```

### Processing Pipeline

1. **Detect Voice**: Continuous listening with automatic phrase segmentation
2. **Voice-to-Text**: Transcribes speech using Whisper (accurate) or PocketSphinx (offline)
3. **Tool Processing**: Two intelligent approaches:
   - **Selector Approach (default)**: 
     - LLM analyzes request and selects appropriate tool(s)
     - Selected tools run in parallel for speed
     - Another LLM formats all outputs into a natural response
   - **Agentic Approach**: 
     - Single agent with direct access to all tools
     - Agent decides when and how to use tools iteratively
4. **Format Result**: Synthesizes tool outputs into conversational response
5. **Speak Result**: Delivers response via text-to-speech

## Available Tools

### 1. **Playwright Agent** (`playwright_agent`)

Intelligent web automation agent with vision capabilities for searching, navigating, and extracting information from websites.

**Example commands:**
- "Search for Python tutorials"
- "Go to python.org and find the latest version"
- "Navigate to GitHub and tell me about trending repositories"

#### How Playwright Agent Works

The playwright agent uses a sophisticated architecture with **3 core components**:

**1. AsyncBrowserSession** - Smart async browser automation
- Built on Playwright (async/await, no blocking, auto-waiting)
- **8+ fallback strategies** for interactions - accepts natural language like "Login button" or "Email field"
- Multi-tab workflow - each navigation opens a new tab
- Stealth mode with anti-detection measures
- Optional video recording for debugging

**2. VisionAnalyzer** - Multimodal LLM vision
- Uses GPT-4o or Claude 3.5 Sonnet to "see" pages like a human
- Analyzes screenshots to understand page layout and identify elements
- Suggests next actions based on goals
- Verifies task completion visually

**3. AdaptiveRetryManager** - Intelligent error recovery
- Adapts retry strategies based on error patterns

#### Agent Tools: 6 Consolidated Actions

Instead of 20+ fragmented tools, the agent uses 6 powerful tools:

1. **`search(query)`** - Search the web, returns URLs
2. **`navigate(url)`** - Go to URL in new tab
3. **`interact(action, target, value)`** - Click, type, or select elements
   - Accepts natural language: "Login", "Email field", "Submit button"
   - Tries 8+ strategies automatically (CSS, text, ARIA, XPath, etc.)
4. **`observe()`** - Analyze page with text + vision
5. **`extract(selector)`** - Get specific content via CSS selector
6. **`verify(question)`** - Check if goal achieved (uses vision)

#### "Observe Before Acting" Workflow

```
1. Understand Goal → Analyze user request
2. Search (if needed) → Find relevant websites  
3. Navigate → Go to URL (opens new tab)
4. OBSERVE FIRST → Use vision + DOM to understand page
5. Interact → Click/type using observed elements
6. Extract → Get specific data
7. Verify → Confirm goal achieved
```

**Example**: Finding latest Python version
```
search("Python version") → navigate(python.org) → observe() 
→ interact("click", "Downloads") → extract(".version") 
→ verify("Have version?") → Return "Python 3.12.0"
```

**Key advantages**: Vision-enhanced understanding, natural language selectors, automatic retries, multi-tab context preservation

### 2. **Calculator** (`calculator`)
Performs mathematical calculations with natural language understanding.

**Example commands:**
- "Calculate 25 times 4"
- "What's 15 plus 37?"
- "Compute 100 divided by 5"
- "What's 2 to the power of 8?"

### 3. **DateTime** (`datetime`)
Provides current time, date, and day information.

**Example commands:**
- "What time is it?"
- "What's today's date?"
- "What day is it?"

### 4. **Search Tool** (`search_tool`)
Fast web search across multiple search engines simultaneously (Google, DuckDuckGo). Returns aggregated results with deduplication.

**Example commands:**
- "Search for Python tutorials"
- "Find information about climate change"
- "Look up Python documentation on python.org"
- "Find PDF papers about machine learning"

**Note:** Different from playwright_agent - this tool finds URLs and summaries, while playwright_agent browses and extracts detailed content.

### 5. **Gmail** (`gmail`)
Search and read Gmail emails with natural language queries. Requires OAuth2 setup.

**Example commands:**
- "Show my recent emails"
- "Find emails from john"
- "Do I have any unread emails?"

**Setup:** Place `oauth2_credentials.json` from Google Cloud Console in project root. First run opens browser for authentication.

## Adding Custom Tools

### 1. Create Your Tool

Create a file in `tools/` directory (e.g., `tools/my_tool.py`):

```python
from tools.base import BaseTool
from typing import Optional

class MyTool(BaseTool):
    """Your custom tool description."""
    
    def __init__(self, enabled: bool = True):
        super().__init__(
            name="my_tool",
            description="Brief one-line description",
            capabilities=(
                "Detailed explanation of what this tool can do. "
                "Be specific - this helps the LLM decide when to use it."
            ),
            enabled=enabled
        )
    
    async def process(self, text: str) -> Optional[str]:
        """Process the input and return result."""
        try:
            result = f"Processed: {text}"
            return result
        except Exception as e:
            print(f"Error in my_tool: {e}")
            return None
```

**Tool Definition:**
- All tools inherit from `BaseTool` (see `tools/base.py`)
- Required attributes:
  - `name`: Unique identifier
  - `description`: Short summary (shown to LLM)
  - `capabilities`: Detailed explanation (helps LLM decide when to use)
- Must implement `async def process(text: str) -> Optional[str]`

### 2. Register Your Tool

In `main.py`, add:

```python
from tools.my_tool import MyTool

# In main() function:
if "my_tool" in settings.enabled_tools:
    my_tool = MyTool(enabled=True)
    processor.register(my_tool)
```

### 3. Enable in Config

Add to `.env`:

```env
ENABLED_TOOLS=["playwright_agent", "my_tool"]
```

## Project Structure

```
jarvis/
├── main.py                      # Entry point - voice assistant loop
├── config.py                    # Configuration management (Pydantic)
├── voice/                       # Voice I/O module
│   ├── stt.py                  # Speech-to-Text (Whisper/PocketSphinx)
│   └── tts.py                  # Text-to-Speech (pyttsx3)
├── tools/                       # Tool system
│   ├── base.py                 # BaseTool abstract class
│   ├── processor.py            # Tool orchestrator with intelligent routing
│   ├── routing.py              # LLM agents for tool selection/formatting
│   ├── playwright_tool.py      # Web automation
│   ├── calculator_tool.py      # Math calculations
│   ├── datetime_tool.py        # Time/date info
│   ├── gmail_tool.py           # Email search
│   └── search_tool.py          # Multi-engine web search
├── playwright_agent/            # Browser automation package
│   ├── agents/                 # Intelligent browser agents
│   ├── core/                   # Browser core, vision analyzer
│   └── search_engines.py       # Multi-engine search manager
└── pyproject.toml              # Dependencies and project config
```

## Configuration Options

### Tool Processing Approach

Choose between two processing approaches in `main.py`:

```python
# Default: Selector approach (explicit tool selection + formatting)
processor = ToolProcessor(approach="selector")

# Alternative: Native/Agentic approach (agent with direct tool access)
processor = ToolProcessor(approach="native")
```

**Selector Approach** (default):
- Clear separation: selection → execution → formatting
- Explicit reasoning about tool choices
- Fast parallel execution
- More LLM calls but transparent logic

**Native/Agentic Approach**:
- Single agent with tool access
- Iterative tool usage
- Fewer LLM calls
- Standard Pydantic AI patterns

## Troubleshooting

### Microphone Issues
```bash
# List available microphones
python -c "import speech_recognition as sr; print(sr.Microphone.list_microphone_names())"
```
Set `MIC_DEVICE_INDEX` in `.env` to the correct index.

### Speech Recognition
- **Whisper errors**: Try smaller model: `WHISPER_MODEL=tiny`
- **Offline alternative**: `USE_WHISPER=false` (uses PocketSphinx)

### TTS Issues
- Check voice preference: `TTS_VOICE_PREFERENCE=david` or `jamie`
- Verify volume: `TTS_VOLUME=1.0`

### OpenAI API
- Required for intelligent routing and some tools
- Get your key at https://platform.openai.com/api-keys

## Platform-Specific Notes

**Windows:**
- PyAudio may need prebuilt wheel from [Gohlke](https://www.lfd.uci.edu/~gohlke/pythonlibs/)

**macOS:**
```bash
brew install portaudio
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt-get update
sudo apt-get install -y portaudio19-dev python3-pyaudio
```


## Contributing

Contributions welcome! Please:
1. Keep code clean and simple
2. Follow existing patterns
3. Update documentation
4. Test your changes

---

**Main Script**: `main.py` - Run with `uv run main.py`

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
