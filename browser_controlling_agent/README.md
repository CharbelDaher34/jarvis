# Enhanced Browser Controlling Agent

A sophisticated browser automation agent powered by PydanticAI, featuring multiple search engines, advanced error handling, performance monitoring, and enhanced user experience.

## 🚀 Features

### 🔧 **Core Capabilities**
- **Multi-Engine Search**: Google, DuckDuckGo, and Bing search integration
- **Smart Browser Automation**: Intelligent element detection and interaction
- **Advanced Error Handling**: Retry mechanisms, circuit breakers, and graceful degradation
- **Performance Monitoring**: Real-time resource usage tracking and optimization
- **Progress Tracking**: Visual progress indicators and detailed logging
- **Security Features**: URL validation, domain filtering, and safe execution

### 🤖 **AI Model Support**
- OpenAI GPT models (GPT-4, GPT-3.5)
- Google Gemini (Gemini Pro, Gemini Flash)
- Anthropic Claude
- Local Ollama models
- Automatic model selection based on available API keys

### 🌐 **Browser Features**
- Chrome automation with Helium and Selenium
- Multi-tab management with automatic cleanup
- Cookie and popup handling
- Form filling and dropdown selection
- Screenshot capture with error reporting
- Smart element waiting and detection

## 📦 Installation

### Prerequisites
```bash
# Python 3.8+ required
python --version

# Install required system dependencies
# On Windows: Chrome browser should be installed
# On Linux: 
sudo apt-get update
sudo apt-get install -y chromium-browser

# On macOS:
brew install --cask google-chrome
```

### Python Dependencies
```bash
# Install the package dependencies
pip install pydantic-ai
pip install helium
pip install selenium
pip install webdriver-manager
pip install googlesearch-python
pip install duckduckgo-search  # Optional
pip install requests           # For Bing search
pip install psutil            # For performance monitoring
pip install python-dotenv     # For environment management
```

### Environment Setup
1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` with your API keys:
```env
# At least one API key is required
OPENAI_API_KEY=sk-your-openai-key-here
GEMINI_API_KEY=your-gemini-api-key-here
ANTHROPIC_API_KEY=your-anthropic-key-here

# Optional: Bing Search API (for advanced search features)
BING_SEARCH_API_KEY=your-bing-api-key-here

# Browser Configuration
BROWSER_HEADLESS=false
BROWSER_WIDTH=1200
BROWSER_HEIGHT=800

# Model Preference
PREFERRED_MODEL=auto  # auto, openai, gemini, anthropic, ollama
```

## 🎯 Usage

### Basic Usage

```python
import asyncio
from src.browser_agent.runner import run_task

# Simple search and navigation
async def main():
    result = await run_task(
        "Search for the best restaurants in New York and visit the first result",
        headless=False
    )
    print(result)

asyncio.run(main())
```

### Command Line Usage

```bash
# Basic usage
python main.py "Find information about climate change on Wikipedia"

# Headless mode
python main.py "Search for Python tutorials" --headless

# With specific configuration
BROWSER_HEADLESS=true python main.py "Get news headlines from BBC"
```

### Advanced Usage Examples

#### 1. Restaurant Search with Filtering
```python
prompt = """
I'm looking for Italian restaurants in San Francisco that:
1. Have ratings above 4 stars
2. Accept reservations online
3. Are open tonight

Search multiple sites, compare options, and provide me with the top 3 recommendations with:
- Name and address
- Rating and review count  
- Reservation link if available
- Price range
"""

result = await run_task(prompt, headless=False)
```

#### 2. Research and Data Collection
```python
prompt = """
Research the latest developments in artificial intelligence:
1. Search for recent AI news (last 30 days)
2. Visit top 5 tech news sites
3. Look for information about:
   - New AI model releases
   - AI research breakthroughs
   - Industry partnerships
4. Summarize key findings with source links
"""

result = await run_task(prompt)
```

#### 3. E-commerce Price Comparison
```python
prompt = """
I want to buy a laptop with these specifications:
- 16GB RAM minimum
- SSD storage 512GB+
- Intel i7 or AMD Ryzen 7 processor
- Budget: $1000-1500

Search on Amazon, Best Buy, and Newegg.
Compare prices and specifications.
Find the best deals and check availability.
"""

result = await run_task(prompt)
```

## 🛠️ Available Tools

### Search Tools
- **`tool_enhanced_search`**: Multi-engine search with filtering
- **`tool_multi_engine_search`**: Compare results across engines
- **`tool_google_search`**: Legacy Google search (fallback)

### Navigation Tools
- **`tool_go_to`**: Navigate to specific URL
- **`tool_go_back`**: Navigate to previous page
- **`tool_smart_click`**: Intelligent element clicking
- **`tool_scroll_down`**: Scroll page content
- **`tool_scroll_to_element`**: Scroll to specific element

### Interaction Tools
- **`tool_fill_form`**: Fill form fields
- **`tool_select_dropdown`**: Select dropdown options
- **`tool_handle_cookies`**: Manage cookie consent
- **`tool_close_popups`**: Close modal dialogs

### Information Tools
- **`tool_get_page_text`**: Extract page content
- **`tool_get_page_info`**: Get page metadata
- **`tool_search_item_ctrl_f`**: Find text on page
- **`tool_wait_for_element`**: Wait for elements to appear

### System Tools
- **`tool_get_performance_info`**: Monitor resource usage
- **`tool_cleanup_resources`**: Free up memory and resources
- **`tool_execute_python`**: Execute custom automation code

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `OPENAI_API_KEY` | OpenAI API key | None | `sk-...` |
| `GEMINI_API_KEY` | Google Gemini API key | None | `AIza...` |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key | None | `sk-ant-...` |
| `PREFERRED_MODEL` | Preferred AI model | `auto` | `openai`, `gemini` |
| `BROWSER_HEADLESS` | Run browser in headless mode | `false` | `true` |
| `BROWSER_WIDTH` | Browser window width | `1200` | `1920` |
| `BROWSER_HEIGHT` | Browser window height | `800` | `1080` |
| `PAGE_LOAD_TIMEOUT` | Page load timeout (seconds) | `30` | `60` |
| `MAX_SEARCH_RESULTS` | Max search results per query | `10` | `20` |
| `LOG_LEVEL` | Logging verbosity | `INFO` | `DEBUG` |
| `ENABLE_SCREENSHOTS` | Enable screenshot capture | `true` | `false` |

### Security Configuration

```env
# Domain Security
ALLOWED_DOMAINS=          # Comma-separated list (empty = allow all)
SSL_VERIFY=true          # Verify SSL certificates
MAX_REDIRECTS=5          # Maximum redirects to follow

# Resource Limits  
MAX_MEMORY_MB=2048       # Maximum system memory usage
MAX_CPU_PERCENT=80       # Maximum CPU usage threshold
MAX_BROWSER_MEMORY_MB=1024  # Maximum browser memory
```

### Search Engine Configuration

```env
# Default search engine
DEFAULT_SEARCH_ENGINE=google  # google, duckduckgo, bing

# Bing Search API (optional)
BING_SEARCH_API_KEY=your-key-here

# Search behavior
SEARCH_CACHE_TTL=300     # Cache results for 5 minutes
```

## 🔍 Advanced Features

### Multi-Engine Search

The agent supports multiple search engines with automatic fallback:

```python
# Search with specific engine
await tool_enhanced_search(
    "artificial intelligence trends 2024",
    engine="duckduckgo",
    num_results=10,
    time_filter="month"
)

# Multi-engine comparison
await tool_multi_engine_search(
    "best programming languages 2024",
    num_results=5
)
```

### Performance Monitoring

Monitor resource usage in real-time:

```python
# Get performance report
performance_info = await tool_get_performance_info()

# Force cleanup when needed
await tool_cleanup_resources()
```

### Error Handling and Retry Logic

Built-in retry mechanisms handle common failures:

- Network timeouts with exponential backoff
- Element not found with multiple detection strategies  
- Browser crashes with automatic recovery
- API rate limits with intelligent delays

### Progress Tracking

Visual progress indicators show operation status:

```
🔄 Initialize browser...
✅ Initialize browser - Completed (2.3s)

🔄 Running task: Search for restaurants...
✅ Running task: Search for restaurants... - Completed (15.7s)
   → Generated 1,247 characters of output

📊 Browser Automation Task Summary:
   • Total time: 18.2s
   • Steps completed: 2/2
```

## 🐛 Troubleshooting

### Common Issues

#### 1. Browser Won't Start
```bash
Error: Browser initialization failed
```

**Solutions:**
- Ensure Chrome is installed and up-to-date
- Check if Chrome is already running (close all instances)
- Try running with `--headless` flag
- On Linux, install chromium-browser: `sudo apt install chromium-browser`

#### 2. API Key Issues
```bash
Error: No API keys found
```

**Solutions:**
- Verify API key format in `.env` file
- Ensure environment variables are loaded properly
- Try with a different model: `PREFERRED_MODEL=ollama`
- Check API key validity and quotas

#### 3. Search Failures
```bash
Error: All search engines failed
```

**Solutions:**
- Check internet connection
- Verify search packages are installed: `pip install googlesearch-python duckduckgo-search`
- Try single engine: `engine="google"`
- Check for rate limiting (wait and retry)

#### 4. Element Not Found
```bash
Error: Could not find or click element
```

**Solutions:**
- Page may still be loading (increase timeout)
- Element might be hidden or disabled
- Try different element description
- Use `tool_wait_for_element` first

### Performance Issues

#### High Memory Usage
```python
# Monitor memory usage
await tool_get_performance_info()

# Force cleanup
await tool_cleanup_resources()
```

#### Slow Page Loading
```env
# Disable images for faster loading
BROWSER_DISABLE_IMAGES=true

# Increase timeout
PAGE_LOAD_TIMEOUT=60
```

### Debugging Tips

#### Enable Debug Logging
```env
LOG_LEVEL=DEBUG
```

#### Disable Headless Mode
```env
BROWSER_HEADLESS=false
```

#### Capture Screenshots on Errors
```env
SCREENSHOT_ON_ERROR=true
```

## 🔒 Security Considerations

### Domain Filtering
```env
# Only allow specific domains
ALLOWED_DOMAINS=wikipedia.org,github.com,stackoverflow.com

# Block specific domains (malware, etc.)
BLOCKED_DOMAINS=malware.com,phishing.com
```

### Safe Execution
- All URLs are validated before navigation
- Automatic popup and malware detection
- SSL certificate verification
- Resource usage monitoring prevents system overload

## 📈 Performance Optimization

### Memory Management
- Automatic browser cache clearing
- Old tab cleanup (configurable timeout)
- Garbage collection on resource pressure
- Memory usage monitoring and alerts

### Speed Optimizations
- Result caching (5-minute default TTL)
- Parallel search engine queries
- Intelligent element waiting
- Image loading can be disabled

### Resource Limits
```env
MAX_MEMORY_MB=2048       # System memory limit
MAX_BROWSER_MEMORY_MB=1024  # Browser memory limit  
MAX_CPU_PERCENT=80       # CPU usage limit
```

## 🤝 Contributing

### Development Setup
```bash
# Clone repository
git clone <repository-url>
cd browser_controlling_agent

# Install development dependencies
pip install -e .
pip install pytest black mypy

# Set up pre-commit hooks
pre-commit install
```

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test category
pytest tests/test_search.py
```

### Code Quality
```bash
# Format code
black src/

# Type checking
mypy src/

# Linting
flake8 src/
```

## 📄 License

MIT License - see LICENSE file for details.

## 🆘 Support

For issues, questions, or feature requests:

1. **Check the troubleshooting guide** above
2. **Search existing issues** in the repository
3. **Create a new issue** with detailed information:
   - Error messages and logs
   - Environment configuration
   - Steps to reproduce
   - Expected vs actual behavior

## 🔄 Changelog

### v2.0.0 - Enhanced Release
- ✨ Multi-engine search support
- 🛡️ Advanced error handling and retry logic
- 📊 Performance monitoring and resource management
- 🎨 Enhanced user experience with progress tracking
- 🔒 Security improvements and domain filtering
- 📚 Comprehensive documentation and examples

### v1.0.0 - Initial Release
- Basic browser automation with Helium
- Google search integration
- Simple agent implementation
- Basic error handling

---

**Happy Automating! 🤖**