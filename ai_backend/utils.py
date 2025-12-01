# Copyright (c) 2025 Mory K Diane
# Licensed under MIT License with Commons Clause
# See LICENSE file in the project root for full license information.

import os
import json
from dotenv import load_dotenv
from datetime import datetime
import requests
from transformers import AutoTokenizer
from vllm.v1.engine.async_llm import AsyncLLM
from vllm import SamplingParams
from vllm.sampling_params import RequestOutputKind
from vllm.engine.arg_utils import AsyncEngineArgs
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich.live import Live
import uuid

# Load .env file
load_dotenv()

# Custom Rich theme for markdown rendering
from rich.theme import Theme
custom_theme = Theme({
    "markdown.item.bullet": "bold magenta",  # 1. ordered list numbers
    "markdown.item.number": "bold red",  # 1. ordered list numbers
    "markdown.em": "italic purple",   # *italic*
    "markdown.strong": "bold blue",   # **bold**
    "markdown.link": "underline blue",   # [text](url)
    "markdown.code": "yellow",           # inline `code`
    "markdown.code_block": "green",      # fenced code blocks
    "markdown.h1": "bold underline bright_white",  # # Header 1
    "markdown.h2": "bold underline bright_white",  # ## Header 2
})

console = Console(theme=custom_theme, force_terminal=True, height=1000, color_system="truecolor")


BASE_INSTRUCTION = (
    "You are cli-assist, my articulate, precise, detailed and elegant assistant with broad knowledge. "
    "Do not add unsolicited advice, reminders, or suggestions. "
    "You are not an AI model; identify only as cli-assist. "
    "Always answer clearly and in organized fashion, with details "
    "and emphasizing important terms and context. Provide examples when they improve unde "
    "use a few emojis. "
    "If you don't know the answer, say so. If the question is not clear, ask for clarification. "
)

class LocalAI:

    def __init__(self, model_name="meta-llama/Llama-3.2-3B-Instruct"):
        engine_args = AsyncEngineArgs(
            model=model_name,
            max_model_len=7500,
            dtype="bfloat16",  # or "bf16",
            gpu_memory_utilization= 0.5, #  50% of GPU memory instead of 90%
        )
        self.engine = AsyncLLM.from_engine_args(engine_args)
        # Load tokenizer for chat template
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)

    def messages_to_prompt(self, messages):
        return self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
    
    def _parse_table(self, text: str):
        """Detect and parse Markdown-style tables into a Rich Table."""
        lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
        if not lines or "|" not in lines[0]:
            return None  # Not a table

        # Basic validation: at least 2 lines (headers + separator + row)
        if len(lines) < 2:
            return None

        # Split rows
        rows = [line.split("|")[1:-1] for line in lines if "|" in line]
        rows = [[cell.strip() for cell in row] for row in rows]

        if len(rows) < 2:
            return None

        headers, *data_rows = rows

        table = Table(show_header=True)
        for header in headers:
            table.add_column(header)

        for row in data_rows:
            table.add_row(*row)

        return table
    
    async def query(self, prompt: str, max_tokens=2048, temperature=0.5, silent = False, silent_tokens =512):
        messages = [
            {"role": "system", "content": BASE_INSTRUCTION},
            {"role": "user", "content": prompt}
        ]
        prompt_str = self.messages_to_prompt(messages)

        sampling_params = SamplingParams(
            max_tokens=max_tokens,
            temperature=temperature,
            output_kind=RequestOutputKind.DELTA,
            repetition_penalty=1.2,  # high practical penalty
        )

        request_id = f"cliassist-{uuid.uuid4().hex[:8]}"
        if silent:
            # Collect the output internally instead of streaming to console
            response_text = ""
            async for chunk in self.engine.generate(prompt=prompt_str, sampling_params=SamplingParams(
            max_tokens=silent_tokens,
            temperature=temperature,
            output_kind=RequestOutputKind.DELTA,
            repetition_penalty=1.4,  # high practical penalty
        ), request_id=request_id):
                for chunk in chunk.outputs:
                    response_text += chunk.text
            return response_text.strip()
        
        assistant_text = ""
        print()
        prefix = "🔴 : "

        # Use Rich Live to continuously refresh Markdown
        with Live(console=console, refresh_per_second=20,auto_refresh=True) as live:
        
            async for output in self.engine.generate(
                request_id=request_id,
                prompt=prompt_str,
                sampling_params=sampling_params
            ):
                for completion in output.outputs:
                    new_text = completion.text
                    if new_text:
                        assistant_text += new_text
                        # Prepend prefix for display
                        display_text = f"{prefix}{assistant_text}"
                        # --- Detect if the text looks like a Markdown table ---
                        table_obj = self._parse_table(assistant_text)
                        if table_obj:
                            # Render the table normally, no colors
                            normal_table = Table(show_header=True)
                            for header in table_obj.columns:
                                normal_table.add_column(header.header)  # default style

                            for row in table_obj.rows:
                                normal_table.add_row(*[str(cell) for cell in row])

                            live.update(normal_table)

                        else:
                            # Otherwise render as styled Markdown
                            md = Markdown(display_text)
                            live.update(md)

        return assistant_text.strip()


class SearchManager:
    def __init__(self, max_searches=250, state_file="search_state.json"):
        self.serpapi_api_key = os.getenv("SERPAPI_API_KEY")
        self.duckduckgo_url = "https://api.duckduckgo.com/"
        self.max_searches = max_searches
        self.state_file = state_file
        self.state = self.load_state()
        self.search_count = self.state["count"]

    def load_state(self):
        if os.path.exists(self.state_file):
            with open(self.state_file, "r") as f:
                return json.load(f)
            
        # Initialize if no file exists
        return {"month": datetime.now().month, "year": datetime.now().year, "count": 0}

    def save_state(self):
        with open(self.state_file, "w") as f:
            json.dump(self.state, f)


    def reset_counter_if_new_month(self):
        now = datetime.now()
        if now.month != self.state["month"] or now.year != self.state["year"]:
            self.state["month"] = now.month
            self.state["year"] = now.year
            self.state["count"] = 0
            self.search_count = 0
            self.save_state()

    def serpapi_search(self, query):

        # Reset if new month
        self.reset_counter_if_new_month()

        if self.search_count >= self.max_searches:
            return None  # Fallback

        # Increment counter since we are using SerpAPI
        self.search_count += 1
        self.state["count"] = self.search_count
        self.save_state()

        params = {
            "q": query,
            "api_key": self.serpapi_api_key,
            "engine": "google",
            "num": 5,
        }

        response = requests.get("https://serpapi.com/search", params=params)

        if response.status_code != 200:
            return f"SerpAPI error: {response.status_code}"

        data = response.json()
        # Extract and format the results however you like:
        results = []
        for result in data.get("organic_results", []):
            title = result.get("title")
            snippet = result.get("snippet")
            link = result.get("link")
            results.append(f"{title}\n{snippet}\n{link}")

        return "\n\n".join(results)

    def duckduckgo_search(self, query):
        params = {
            "q": query,
            "format": "json",
            "no_redirect": 1,
            "no_html": 1,
            "skip_disambig": 1,
        }
        response = requests.get(self.duckduckgo_url, params=params)
        if response.status_code != 200:
            return f"DuckDuckGo error: {response.status_code}"

        data = response.json()
        abstract = data.get("AbstractText", "")
        related = data.get("RelatedTopics", [])
        if abstract:
            return abstract
        elif related:
            return related[0].get("Text", "")
        else:
            return "No results found."

    def search(self, query):
        # Try SerpAPI first
        result = self.serpapi_search(query)

        # If SerpAPI fails (either max searches reached or network/API error), fallback to DuckDuckGo
        if result is None:
            return self.duckduckgo_search(query)

        return result



search_manager = SearchManager()


