[![Latest Release](https://img.shields.io/github/v/release/myro-aiden/cli-assist)](https://github.com/myro-aiden/cli-assist/releases)
# cli-assist 🔴

A framework, a personal terminal-based AI assistant that combines local LLM inference with real-time web search capabilities and endless potential tools. This tool, when offline, is bound to privacy as its operations are entirely hosted, and so reliant on your own machine. Powered by vLLM, CUDA and a local LLM (Meta Llama 3.2 3B in this case), cli-assist provides articulate, detailed responses with internet-sourced context when needed. This open-source version allows users to develop and add functionality to their liking.

## Features

- **Local LLM Inference**: Currently Runs Llama 3.2 3B Instruct (Other models can be used, pipeline may need to be updated for other-than Llama models) locally using vLLM for fast, private inference
- **Smart Web Search**: Detects when online information is needed (through keywords, this method can be upgraded) (news, current events, data, trends, etc.)
- **Session Memory**: Maintains conversation history and automatically generates summaries and titles
- **Rich Terminal UI**: Beautiful formatted output with syntax highlighting, tables, and live rendering, still needs expanding and polishing
- **Chat Interface**: Arrow-key navigation, multi-turn conversations, session management
- **Dynamic URL Filtering**: Heuristic-based filtering to prioritize quality sources (academic, government, documentation) (Can be upgraded/deepened to access more internet content)
- **Content Quality Assessment**: Evaluates scraped content for accessibility and paywall detection

## Installation

### System Requirements

**⚠️ Currently Linux-only** (Native Windows not tested and has limitations/macOS support planned)

- WSL on Windows or Linux OS (Ubuntu 20.04 LTS for WSL Tested, Debian 11+ and others untested but should work)
- Python 3.10+ (3.11 Recommended)
- NVIDIA GPU with 4GB+ VRAM (recommended)
- 8GB RAM minimum
- CUDA 12.8 (Recommended)

**✅ Currently tested on:**
- CPU: AMD Ryzen 7 7800X3D 8-Core Processor
- GPU: NVIDIA GeForce RTX 4080
- RAM: 64GB DDR5 6000 MT/s
- Windows 11
- WSL (Ubuntu 20.04 LTS)

## Setup

### Ubuntu 20.04 LTS on WSL:
1. Open / Enter WSL or your Linux system:
```bash
WSL
```
2. Add the deadsnakes repository for Python 3.11:
```bash
</> WSL
sudo add-apt-repository ppa:deadsnakes/ppa
```
3. Install initial dependencies:
```bash
</> WSL
sudo apt install python3.11 python3.11-dev python3.11-venv python3-pip git build-essential
```
4. 
```bash
</> WSL
sudo apt update
```
5. 
```bash
</> WSL
sudo apt upgrade
```
6. Clone the repository from GitHu
```bash
</> WSL
git clone https://github.com/myro-aiden/cli-assist.git
```
7. 
```bash
</> WSL
cd cli-assist
```
8. 
```bash
</> WSL
python3.11 -m venv "venv"
``` 

### Next, from within the venv:
1. Download CUDA Toolkit 12.8 for your distro (https://developer.nvidia.com/cuda-12-8-0-download-archive) (Delete the leftover .deb file)
2. Download PyTorch for CUDA 12.8 (https://pytorch.org/get-started/locally/)
3. Download the following packages to facilitate flash-attention (https://github.com/Dao-AILab/flash-attention)
```bash
</> WSL
pip install -U pip psutil wheel setuptools packaging ninja
```
4. Download required libraries:
```bash
</> WSL
MAX_JOBS=4 uv pip install -r requirements.txt --no-build-isolation
```
This will take a while in most cases due to FlashAttention, check link in previous step. It SHOULD work, but if you cannot wait, or it simply doesn't, remove "flash_attn==2.8.3" from requirements.txt and run: 
```bash
</> WSL
uv pip install -r requirements.txt
```
5. Install in editable mode:
```bash
</> WSL
pip install -e .
```
This will:

a. Install all dependencies

b. Download the Llama 3.2 3B Instruct model on first run (You will need to request access (https://huggingface.co/meta-llama/Llama-3.2-3B) and then import a Hugging Face token for this model through the Hugging Face CLI (https://huggingface.co/docs/huggingface_hub/en/guides/cli)  prior) & install hf_transfer:
```bash
</> WSL
hf auth login
pip install hf_transfer
```
c. Create a `cliassist` command-line entry point, this entry point can be renamed and configured in setup.py (You would run the script by entering this name within the venv)

### Environment Variables

Create a `.env` file in the project root:

```bash
</>.env
SERPAPI_API_KEY=your_api_key_here (Register for key (https://serpapi.com/))
```

**Note**: SerpAPI is optional, but I recommend you use it because there is a counter integrated that ensures the limit 250 searches per month is not exceeded, which rarely is. If not set or quota is exceeded, the app falls back to DuckDuckGo.

## Usage

![Demo](docs/assets/cliassist.gif)

## Architecture
### Core Components

- **`ai\_backend/\_\_main\_\_.py`**: Entry point
- **`ai\_backend/cliassist.py`**: Main CLI application and conversation loop
- **`ai\_backend/utils.py`**:
- `LocalAI`: Async wrapper around vLLM for LLM inference
- `SearchManager`: Handles web search (SerpAPI + DuckDuckGo fallback)
- `DynamicURLFilter`: Scores and filters URLs by quality
- `ContentQualityAssessor`: Evaluates scraped content

### Conversation Flow

```
System Input (Base Instructions, Context Engineering)
    **↓**

User Input
    **↓**

Detect if search needed (keyword heuristics)
    **↓**

[Optional] Fetch + summarize URLs
    **↓**

Build prompt with inputs and online info + session context if any
    **↓**

Query LLM (vLLM, CUDA)
    **↓**

Stream response with Rich formatting
    **↓**

Update session memory
```


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
Ultimately, thisi is designed for you to use any model youd like but it will need to be tweeked depending on the model's function. The curent code is suitable for text-to-text models.

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
- **Terminal Width**: Your terminal width must be at least as wide as you specify in code [`utils.py:L38`](https://github.com/myro-aiden/cli-assist/blob/468d30320cb82245eae50081f568568970301598/ai_backend/utils.py) 

## Troubleshooting
Traceback calls often suffice to understand and solve most issues

### Out of Memory
Reduce `gpu_memory_utilization` or `max_model_len` in `utils.py` (Read Traceback)

### Web Search Not Working
- Check SerpAPI quota: https://serpapi.com/account
- Verify `.env` file exists with valid API key
- App will fallback to DuckDuckGo automatically

### Entry Point Not Found
Reinstall the package:
```bash
pip install -e .
```

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
This is yours to build upon, a paid version might come out with extras, but this can be what you want it to be for yourself. I am always open to offers should you like to sell this somehow.

## Author

Created by Mory K Diane

- GitHub: @myro-aiden (https://github.com/myro-aiden)
- Also known as: cramoisi