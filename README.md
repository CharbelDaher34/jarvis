# Jarvis Voice Assistant

A modular voice-controlled assistant with extensible tool system for web automation and more.

## Features

- 🎤 **Continuous listening** with automatic phrase segmentation
- 🗣️ **Speech-to-Text** using Whisper or PocketSphinx
- 🔊 **Text-to-Speech** with pyttsx3
- 🤖 **Intelligent tool routing** - LLM selects the best tools for each task
- ⚡ **Parallel execution** - runs multiple tools concurrently
- 🛠️ **Extensible tool system** - easily add/remove capabilities
- 🌐 **Web automation** via playwright_agent
- ⚙️ **Configurable** via environment variables

## Project Structure

```
jarvis/
├── main.py                    # Entry point
├── config.py                  # Configuration management
├── voice/                     # Voice I/O module
│   ├── stt.py                # Speech-to-Text
│   └── tts.py                # Text-to-Speech
├── tools/                     # Tool system
│   ├── base.py               # BaseTool interface
│   ├── processor.py          # Tool orchestrator
│   └── playwright_tool.py    # Web automation tool
├── playwright_agent/          # Browser automation package
│   ├── agents/
│   ├── core/
│   └── ...
└── improved_usage.py          # Playwright agent examples
```

## Installation

### Prerequisites

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone repository
git clone <repo-url>
cd jarvis
```

### Install Dependencies

```bash
# Install Python packages
uv add SpeechRecognition pyttsx3 pyaudio

# For Whisper support (optional, but recommended)
uv add torch whisper soundfile numpy

# For PocketSphinx (offline STT alternative)
uv add pocketsphinx
```

### Platform-Specific Notes

**Windows:**
- PyAudio might need prebuilt wheel from [Gohlke](https://www.lfd.uci.edu/~gohlke/pythonlibs/)

**macOS:**
```bash
brew install portaudio
uv add pyaudio
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt-get update
sudo apt-get install -y portaudio19-dev python3-pyaudio
uv add pyaudio
```

## Configuration

Create a `.env` file in the project root with your settings:

```env
# OpenAI API Key (required for playwright_agent)
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

# Tools
ENABLED_TOOLS=["playwright_agent"]
PLAYWRIGHT_HEADLESS=true
```

**Important**: The `playwright_agent` requires an OpenAI API key. Get yours at https://platform.openai.com/api-keys

## Usage

### Run the Assistant

```bash
uv run main.py
```

The assistant will:
1. Calibrate for ambient noise
2. Wait for your voice
3. Transcribe your speech
4. Use LLM to intelligently select appropriate tools
5. Execute selected tools in parallel
6. Format and speak the result back

### Exit

Say any stop word (`stop`, `quit`, `exit`) or press `Ctrl+C`.

## Adding New Tools

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
            description="Brief one-line description of what the tool does",
            capabilities=(
                "Detailed description of the tool's capabilities. "
                "This helps the LLM decide when to use this tool. "
                "Be specific about what tasks it can handle."
            ),
            enabled=enabled,
            priority=50  # Used as fallback if routing fails
        )
    
    async def process(self, text: str) -> Optional[str]:
        """Process the input and return result."""
        try:
            # Your tool logic here
            result = f"Processed: {text}"
            return result
        except Exception as e:
            print(f"Error in my_tool: {e}")
            return None
```

**Key Points:**
- `description`: Short, clear summary (shown to LLM)
- `capabilities`: Detailed explanation of what the tool can do
- The LLM automatically decides when to use your tool based on these descriptions
- No need for `should_process()` - intelligent routing handles it!

### 2. Register Your Tool

In `main.py`, add your tool:

```python
from tools.my_tool import MyTool

# In main() function, after creating processor:
if "my_tool" in settings.enabled_tools:
    my_tool = MyTool(enabled=True)
    processor.register(my_tool)
```

### 3. Enable in Configuration

Add to your `.env` or `config.py`:

```env
ENABLED_TOOLS=["playwright_agent", "my_tool"]
```

## How Intelligent Routing Works

When you speak a command, Jarvis uses a 3-step process:

1. **Selection**: An LLM analyzes your request and selects the most appropriate tool(s) based on their descriptions and capabilities
2. **Execution**: Selected tools run in parallel (concurrently) for speed
3. **Formatting**: Another LLM synthesizes all tool outputs into a natural, conversational response

**Benefits:**
- Automatically chooses the right tool for the job
- Can use multiple tools together when needed
- Fast parallel execution
- Natural language responses

**Example:**
- You say: "Search for Python tutorials and tell me about the latest version"
- Selector LLM: Chooses `playwright_agent` (can search and extract info)
- Executor: Runs web search and extraction
- Formatter: Creates friendly response from results

## Available Tools

### Playwright Agent

Web automation tool for searching, navigating, and extracting information from websites.

**Example commands:**
- "Search for Python tutorials"
- "Go to python.org and find the latest version"
- "Navigate to GitHub and tell me about trending repositories"

**Configure:**
```env
PLAYWRIGHT_HEADLESS=true  # Run without visible browser
```

**See examples:**
```bash
uv run improved_usage.py
```

## Development

### Project Philosophy

- **Simple**: Avoid unnecessary complexity
- **Modular**: Clear separation of concerns
- **Extensible**: Easy to add new capabilities
- **Configurable**: Customize via config, not code changes

### Key Components

1. **Voice Module (`voice/`)**: Handles all speech I/O
2. **Tools System (`tools/`)**: Plugin-like architecture for processing
3. **Configuration (`config.py`)**: Centralized settings management
4. **Main Loop (`main.py`)**: Orchestrates everything

### Testing

Test individual components:

```bash
# Test playwright agent examples
uv run improved_usage.py

# Test voice recognition only
python -c "from voice import SpeechRecognizer; print('Import OK')"

# Test TTS only
python -c "from voice import TextToSpeech; tts = TextToSpeech(); tts.speak('Hello')"
```

## Troubleshooting

### Microphone not detected
```bash
# List available microphones
python -c "import speech_recognition as sr; print(sr.Microphone.list_microphone_names())"
```

Set `MIC_DEVICE_INDEX` in `.env` to the correct index.

### Whisper errors
- Reduce model size: `WHISPER_MODEL=tiny` (faster, less accurate)
- Or use PocketSphinx: `USE_WHISPER=false`

### No sound output
- Check TTS voice preference: `TTS_VOICE_PREFERENCE=david` or `jamie`
- Verify volume: `TTS_VOLUME=1.0`

## License

MIT

## Contributing

Contributions welcome! Please:
1. Keep code clean and simple
2. Follow existing patterns
3. Update documentation
4. Test your changes

---

**Note:** Original `say_and_repeat.py` archived as `say_and_repeat.py.old` for reference.
