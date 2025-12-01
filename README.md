# cli-assist 🔴

A terminal-based AI assistant that combines local LLM inference with real-time web search capabilities. Powered by vLLM and Llama 3.2, cli-assist provides articulate, detailed responses with internet-sourced context when needed. This open-source version allows users to develop and add fuctionality to this cli tool.

## Features

- **Local LLM Inference**: Currently Runs Llama 3.2 3B Instruct (Other models can be used, pipline may need to be updated for other-than Llama models) locally using vLLM for fast, private inference
- **Smart Web Search**: Detects when online information is needed (through keywords, this method can be upgraded) (news, current events, data, trends, etc.)
- **Session Memory**: Maintains conversation history and automatically generates summaries and titles
- **Rich Terminal UI**: Beautiful formatted output with syntax highlighting, tables, and live rendering, still needs expanding and polishing
- **Chat Interface**: Arrow-key navigation, multi-turn conversations, session management
- **Dynamic URL Filtering**: Heuristic-based filtering to prioritize quality sources (academic, government, documentation) (Can be upgrated to access more internet content)
- **Content Quality Assessment**: Evaluates scraped content for accessibility and paywall detection

## Installation

## System Requirements

**⚠️ Currently Linux-only due to vLLM** (Native Windows not tested and has limitations/macOS support planned)

- WSL2 on Windows or Linux OS (Ubuntu 20.04+, Debian 11+, or similar)
- Python 3.10+ (3.11.7)
- NVIDIA GPU with 4GB+ VRAM (recommended)
- 8GB RAM minimum
- CUDA 11.8+

### Setup

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3.11-pip python3.11-venv git
1) Clone the repository from github (git clone https://github.com/myro-aiden/cli-assist.git), then:
cd cli-assist
python3.11 -m venv "venv" #create a venv using python3.11 (Recommended) or the one you choose
pip install -r requirements.txt
# Install in editable mode (installs dependencies and creates `cliassist` command that runs the script)
pip install -e .
```

This will:
1. Install all dependencies (vLLM, transformers, click, etc.)
2. Download the Llama 3.2 3B Instruct model on first run
3. Create a `cliassist` command-line entry point, this entry point can be renamed and setup in setup.py

## Usage

Simply type:

```bash
cliassist
```

Then:
1. **Select a session**: Choose a previous conversation or start a new one
2. **Chat**: Type your questions/prompts
3. **Exit**: Type `exit`, `quit`, or press `Ctrl+C`
4. **Save**: Optionally save the conversation with auto-generated title and summary

**NOTE:** Prepending ! allows you to execute terminal commands outside the "application"
    Example:

    ```bash
    !ls
    ``` 
    will list the content of your present directory (Alot can be done with this.)


### Example Interactions

```
🔴 : cli-assist ready. type 'exit' or similar to quit.

User: What are the latest developments in AI?
🔴 : [Searches the web and responds with current information]

User: Tell me more about the transformer architecture
🔴 : [Uses local context from the model, no search needed]

User: What happened in the markets today?
🔴 : [Detects keyword for web search, fetches latest financial data]
```

## Architecture
### Core Components

- **`ai_backend/__main__.py`**: Entry point
- **`ai_backend/cliassist.py`**: Main CLI application and conversation loop
- **`ai_backend/utils.py`**: 
  - `LocalAI`: Async wrapper around vLLM for LLM inference
  - `SearchManager`: Handles web search (SerpAPI + DuckDuckGo fallback)
  - `DynamicURLFilter`: Scores and filters URLs by quality
  - `ContentQualityAssessor`: Evaluates scraped content

### Conversation Flow

```
User Input
    ↓
Detect if search needed (keyword heuristics)
    ↓
[Optional] Fetch + summarize URLs
    ↓
Build prompt with session context + online info
    ↓
Query LLM (vLLM)
    ↓
Stream response with Rich formatting
    ↓
Update session memory
```

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
SERPAPI_API_KEY=your_api_key_here
```

**Note**: SerpAPI is optional, but I recommend you use it because there is a counter intigrated that ensures the limit 250 searches per month is not exceeded which is alot already. If not set or quota is exceeded, the app falls back to DuckDuckGo.

### Model Settings

Edit `ai_backend/utils.py` to change:

- **Model**: Change `model_name` in `LocalAI.__init__`
- **Max tokens**: Adjust `max_model_len` (default: 7500)
- **GPU memory**: Change `gpu_memory_utilization` (default: 0.5)
- **Temperature**: Adjust inference temperature for creativity

```python
engine_args = AsyncEngineArgs(
    model="meta-llama/Llama-3.2-3B-Instruct",  # Change model here
    max_model_len=7500,  # Adjust context length
    dtype="bfloat16",
    gpu_memory_utilization=0.5,  # GPU memory percentage
)
```

## Session Management

Sessions are stored in the `memory/` directory as JSON files with format:

```json
{
  "created_at": "2025-11-30T10:15:30",
  "title": "Discussion about quantum computing",
  "summary": "Covered quantum entanglement, decoherence, and NISQ algorithms...",
  "messages": [
    {"user": "What is quantum computing?", "ai": "Quantum computing leverages..."},
    ...
  ]
}
```

- Sessions auto-save with timestamps
- Auto-generated titles and summaries
- Arrow-key menu to browse and resume sessions

## Performance Notes

- **First run**: Model downloads (~7GB) and initializes (may take 2-3 minutes)
- **Subsequent runs**: Start in ~30 seconds
- **Inference speed**: ~10-50 tokens/second depending on GPU
- **GPU memory**: ~6-8GB with 50% utilization setting


## Troubleshooting
Traceback calls often suffice to understand and solve most issues

### Model Download Issues
If the model fails to download, manually download it from hugging face Official Website, it should look something like the following:
```bash
huggingface-cli download meta-llama/Llama-3.2-3B-Instruct --local-dir ./models
```

### Out of Memory
Reduce `gpu_memory_utilization` or `max_model_len` in `utils.py`

### Web Search Not Working
- Check SerpAPI quota: https://serpapi.com/account
- Verify `.env` file exists with valid API key
- App will fallback to DuckDuckGo automatically

### Entry Point Not Found
Reinstall the package:
```bash
pip install -e .
```

## Dependencies

- **vllm**: LLM serving engine
- **transformers**: Model tokenizers and utilities
- **prompt-toolkit**: Terminal UI and keybindings
- **rich**: Terminal formatting and tables
- **beautifulsoup4**: HTML parsing
- **readability-lxml**: Content extraction
- **requests**: HTTP requests
- **click**: CLI utilities
- **dotenv**: Environment variable loading

## License

This project is licensed under the MIT License with Commons Clause - see the LICENSE file for details.

### What This Means

- ✅ **Free to use** - Download, modify, and use for personal/non-commercial projects
- ✅ **Open source** - Full source code available
- ✅ **Forkable** - Create your own versions
- ❌ **Cannot resell** - Cannot sell this software as a product or service
- ❌ **No SaaS** - Cannot offer as a hosted/managed service for profit

### Commercial Use

For commercial licensing inquiries, please contact nuagecramoisi@gmail.com

## Attribution

If you use this software, attribution is appreciated:
```
Based on cli-assist by Mory K Diane
https://github.com/myro-aiden/cli-assist
```
## Contributing

Feel free to open issues or PRs for improvements!

## Future Enhancements

This is yours to build upon, a payed version might come out with extras, but this can be what you want it to be for yourself. I am always open to offers should you like to sell this somehow.

## Author

Created by Mory K Diane
- GitHub: @myro-aiden (https://github.com/myro-aiden)
- Also known as: cramoisi
