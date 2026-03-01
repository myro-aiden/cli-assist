# Copyright (c) 2025 Mory K Diane
# Licensed under MIT License with Commons Clause
# See LICENSE file in the project root for full license information.

import asyncio
from datetime import datetime
import re
import subprocess
import time
from urllib.parse import urlparse
import aiohttp
from bs4 import BeautifulSoup
from readability import Document
from prompt_toolkit import PromptSession
from .utils import BASE_INSTRUCTION, LocalAI, SearchManager
from typing import List, Dict, Optional, Tuple
import os
import json, uuid
from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.containers import Window, HSplit
from prompt_toolkit.styles import Style
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.console import Console

MEMORY_FOLDER = "memory"

console = Console()

class StatusBox:
    def __init__(self, title="Task Status"):
        self.messages = []
        self.title = title

    async def log(self, msg: str, live, delay: float = 0.01):
        """Gradually type out a new log line."""
        typed = ""
        # start a new empty line for this message
        self.messages.append("")
        idx = len(self.messages) - 1

        for ch in msg:
            typed += ch
            self.messages[idx] = typed
            live.update(self.render())
            await asyncio.sleep(delay)

        # finalize line
        self.messages[idx] = msg
        live.update(self.render())

    async def clear(self, live, delay: float = 0.05):
        """Shrink animation — clears messages one by one upward."""
        while self.messages:
            self.messages.pop()
            live.update(self.render())
            await asyncio.sleep(delay)

    def render(self):
        """Render the box with all messages."""
        table = Table.grid(padding=(0, 0))
        for msg in self.messages:
            table.add_row(msg)
        return Panel(table, title=self.title, border_style="dim magenta", expand=False)
    
async def terminal_menu(title: str, options: List[Tuple[str, str]]) -> str:
    """
    Generic arrow-key menu for terminal.
    
    options: list of (value, display_text)
    Returns the selected 'value'.
    """
    selected_index = 0
    kb = KeyBindings()

    @kb.add("up")
    def up(event):
        nonlocal selected_index
        selected_index = (selected_index - 1) % len(options)

    @kb.add("down")
    def down(event):
        nonlocal selected_index
        selected_index = (selected_index + 1) % len(options)

    @kb.add("enter")
    def enter(event):
        event.app.exit(result=selected_index)

    def get_menu_text():
        result = [("class:title", title + "\n\n")]
        for i, (_, text) in enumerate(options):
            prefix = "➡ " if i == selected_index else "   "
            style = "class:selected" if i == selected_index else ""
            result.append((style, prefix + text + "\n"))
        return result

    control = FormattedTextControl(get_menu_text)
    container = Window(content=control, always_hide_cursor=True)
    layout = Layout(HSplit([container]))
    style = Style.from_dict({
        "selected": "reverse",
        "title": "bold fg:#FF0000",
    })

    app = Application(layout=layout, key_bindings=kb, full_screen=False, style=style, mouse_support=False)
    index = await app.run_async()
    return options[index][0]

async def select_session() -> Optional[str]:
    """
    Let user pick a session or start a new conversation.
    Returns the session path, or None for a new session.
    """
    sessions = cliassist.list_sessions()
    choices = [("new", "➕ new discussion")]

    for s in sessions:
        display_text = f"📜 [{datetime.fromisoformat(s['created_at']).strftime('%m-%d %H:%M')}] {s['title']}"
        choices.append((s["path"], display_text))

    selected = await terminal_menu("\n🔴 : please pick a convo", choices)
    if selected == "new":
        return None
    return selected

def clean_text(text: str) -> str:
        # Remove emojis and other non-standard symbols
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002700-\U000027BF"  # Dingbats
            "\U0001F900-\U0001F9FF"  # Supplemental Symbols & Pictographs
            "\U00002600-\U000026FF"  # Misc symbols
            "\U00002B00-\U00002BFF"  # Arrows
            "\U00002000-\U000020FF"  # General Punctuation
            "]+",
            flags=re.UNICODE
        )
        return emoji_pattern.sub(r'', text)

async def confirm_save_terminal() -> bool:
    """
    Arrow-key menu: Should we save this session?
    Returns True if 'Yes', False if 'No'
    """
    choice = await terminal_menu(
        "\n🔴 : should I keep this in mind for the future?",
        [("yes", "Yes"), ("no", "No")],
    )
    return choice == "yes"


# ---- Utility: summarization ----
async def generate_summary(local_ai, messages: List[Dict[str, str]]) -> str:
    text = "\n".join(f"User: {m['user']}\n\ncli-assist: {m['ai']}" for m in messages)
    prompt = f"Summarize the ENTIRE conversation below in a concise paragraph, keeping only the key points:\n\n{text}"
    return (await local_ai.query(prompt, silent=True)).strip()


async def generate_title(local_ai, summary: str) -> str:
    prompt = f"Your only function is to create a very short title (5–10 words max) describing the following conversation summary. DO NOT ADD notes, a follow up, emojis or quotaion marks:\n\n{summary}"
    return (await local_ai.query(prompt, silent=True)).strip()

class DynamicURLFilter:
    """Heuristic-based URL filtering without hardcoded lists"""
    
    def score_url(self, url: str) -> tuple[int, str]:
        """Score URL based on multiple heuristics"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower().replace('www.', '')
            path = parsed.path.lower()
            score = 0
            reasons = []
            
            # 1. Domain TLD scoring (institutional trust)
            if any(domain.endswith(tld) for tld in ['.edu', '.ac.uk', '.ac.jp', '.edu.au']):
                score += 15
                reasons.append('educational institution')
            elif any(domain.endswith(tld) for tld in ['.gov', '.mil', '.gov.uk', '.gov.au']):
                score += 15
                reasons.append('government domain')
            elif domain.endswith('.org'):
                score += 8
                reasons.append('organization domain')
            
            # 2. Secure connection
            if url.startswith('https://'):
                score += 2
            
            # 3. Subdomain patterns (official documentation/resources)
            subdomain_patterns = ['docs.', 'developer.', 'api.', 'help.', 'support.', 'blog.', 'news.']
            if any(domain.startswith(pattern) for pattern in subdomain_patterns):
                score += 4
                reasons.append('official subdomain')
            
            # 4. URL path indicates content type
            content_paths = [
                '/article/', '/post/', '/blog/', '/news/', '/story/',
                '/content/', '/publication/', '/research/', '/paper/',
                '/guide/', '/tutorial/', '/documentation/', '/wiki/'
            ]
            if any(pattern in path for pattern in content_paths):
                score += 5
                reasons.append('content-rich path')
            
            # 5. Known high-quality patterns
            quality_patterns = [
                'wikipedia.org', 'britannica.com', 'reuters.com', 'apnews.com',
                'bbc.co', 'npr.org', 'pbs.org', 'nature.com', 'science.org',
                'arxiv.org', 'pubmed', 'ieee.org', 'acm.org', 'stackoverflow.com',
                'github.com', 'mozilla.org'
            ]
            if any(pattern in domain for pattern in quality_patterns):
                score += 10
                reasons.append('recognized quality source')
            
            # 6. Penalize known problematic patterns
            if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.pdf', '.mp4', '.zip']):
                return (0, 'non-HTML resource')
            
            # Social media (unreliable as primary sources)
            social_domains = ['facebook.com', 'twitter.com', 'instagram.com', 'tiktok.com', 'reddit.com']
            if any(social in domain for social in social_domains):
                return (0, 'social media')
            
            # Known paywall indicators in domain
            paywall_indicators = [
                'wsj.com', 'nytimes.com', 'washingtonpost.com', 'ft.com',
                'economist.com', 'bloomberg.com', 'businessinsider.com'
            ]
            if any(paywall in domain for paywall in paywall_indicators):
                score -= 10
                reasons.append('likely paywalled')
            
            # 7. Path depth (too deep often means navigation pages)
            path_depth = len([p for p in path.split('/') if p])
            if path_depth > 5:
                score -= 2
            
            return (score, ', '.join(reasons) if reasons else 'generic scoring')
            
        except Exception as e:
            return (0, f'parsing error: {e}')
    
    def filter_urls(self, urls: list[str], top_n: int = 5) -> list[tuple[str, int, str]]:
        """Filter and rank URLs by quality score"""
        scored = []
        
        for url in urls:
            score, reason = self.score_url(url)
            if score > 0:  # Only include URLs with positive scores
                scored.append((url, score, reason))
        
        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        
        return scored[:top_n]

class ContentQualityAssessor:
    """Assess scraped content quality dynamically"""
    
    def assess_html(self, html: str, url: str) -> dict:
        """Assess if HTML content is worth processing"""
        assessment = {
            'is_accessible': True,
            'is_quality': False,
            'score': 0,
            'issues': []
        }
        
        html_lower = html.lower()
        
        # Check for paywalls
        paywall_terms = [
            'paywall', 'subscription required', 'login required',
            'subscribe to continue', 'premium content', 'become a member',
            'create free account', 'sign up to read', 'subscriber exclusive'
        ]
        if any(term in html_lower for term in paywall_terms):
            assessment['is_accessible'] = False
            assessment['issues'].append('paywall detected')
            return assessment
        
        # Check for access restrictions
        restriction_terms = [
            'access denied', '403 forbidden', '401 unauthorized',
            'not available in your region', 'geo-blocked'
        ]
        if any(term in html_lower for term in restriction_terms):
            assessment['is_accessible'] = False
            assessment['issues'].append('access restriction')
            return assessment
        
        # Check content length (too short = likely blocked or navigation page)
        if len(html) < 1000:
            assessment['issues'].append('content too short')
            return assessment
        
        # Extract and assess main content
        try:
            doc = Document(html)
            content_html = doc.summary()
            soup = BeautifulSoup(content_html, 'html.parser')
            text_content = soup.get_text(separator='\n', strip=True)
            
            text_length = len(text_content)
            
            # Quality indicators
            if text_length > 500:
                assessment['score'] += 3
            if text_length > 1500:
                assessment['score'] += 2
            
            # Check for article indicators
            if any(indicator in html_lower for indicator in ['<article', 'byline', 'author:', 'published']):
                assessment['score'] += 2
            
            # Check ad density (high ads = low quality)
            ad_count = html_lower.count('advertisement') + html_lower.count('ad-container')
            if ad_count > 15:
                assessment['score'] -= 2
                assessment['issues'].append('high ad density')
            
            # Final quality determination
            if assessment['score'] >= 3 and text_length >= 400:
                assessment['is_quality'] = True
            
        except Exception as e:
            assessment['issues'].append(f'parsing error: {str(e)[:50]}')
        
        return assessment

class cliassist:
    def __init__(self, base_instruction=BASE_INSTRUCTION, session_file=None):
        self.local_ai = LocalAI()
        self.search_manager = SearchManager()
        self.base_instruction = base_instruction
        

# Dynamic filtering components
        self.url_filter = DynamicURLFilter()
        self.content_assessor = ContentQualityAssessor()
        
        # Better headers for scraping
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none'
        }

        # Current session state
        self.session_memory: List[Dict[str, str]] = []
        self.summary: str = ""
        self.title: str = ""
        self.session_file: str | None = session_file

        os.makedirs(MEMORY_FOLDER, exist_ok=True)

    async def load_session(self, session_file: str):
        """Load a session memory file without reloading the model."""
        self.session_file = session_file
        #self.session_memory = await self._restore_session_memory(session_file)
        # Optionally load summary or title if stored
        #self.summary, self.title = await self._restore_session_metadata(session_file)

    # ---- MEMORY HANDLERS ----
    # Load an existing session if path provided
        if session_file and os.path.exists(session_file):
            with open(session_file, "r") as f:
                data = json.load(f)
                self.session_memory = data.get("messages", [])
                self.summary = data.get("summary", "")
                self.title = data.get("title", "")
            self.session_file = session_file
        else:
            self.session_file = None

    

    async def update_memory(self, prompt: str, response: str):
        # Keep Unicode letters and punctuation, remove symbols/emojis
        clean_response = clean_text(response)
        self.session_memory.append({"user": prompt, "ai": clean_response})

    async def save_session(self):
        """Save the current session with updated summary + title"""
        if not self.session_memory:
            return None

       
        self.summary = await generate_summary(self.local_ai, self.session_memory)
        self.title = await generate_title(self.local_ai, self.summary)

        
        if not self.session_file:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            uid = uuid.uuid4().hex[:8]  # short unique ID
            session_id = f"{timestamp}_{uid}"
            self.session_file = os.path.join(MEMORY_FOLDER, f"{session_id}.json")

        with open(self.session_file, "w") as f:
            json.dump(
                {
                    "id": os.path.basename(self.session_file).replace(".json", ""),
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                    "title": self.title,
                    "summary": self.summary,
                    "messages": self.session_memory,
                },
                f,
                indent=2,
            )
        type_out(f"🔴 : remembered as '{self.title}'. peace 🌅")
        return self.session_file

    @staticmethod
    def list_sessions() -> List[Dict[str, str]]:
        """Return all saved sessions (id, title, summary, path)"""
        sessions = []
        if not os.path.exists(MEMORY_FOLDER):
            return sessions

        for fname in os.listdir(MEMORY_FOLDER):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(MEMORY_FOLDER, fname)
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                    sessions.append(
                        {
                            "id": data.get("id", fname.replace(".json", "")),
                            "title": data.get("title", "Untitled"),
                            "summary": data.get("summary", ""),
                            "created_at": data.get("created_at", fname.replace(".json", "")),
                        "path": path,
                        }
                    )
            except Exception:
                continue

        # Sort by created_at descending
        sessions.sort(key=lambda x: x["created_at"], reverse=True)
        return sessions

    # ---- MAIN INTERACTION ----
    def should_search_online(self, prompt: str) -> bool:
        # Simple heuristic for deciding if we need the internet
        keywords = [
            "current",
            "latest",
            "today",
            "news",
            "update",
            "stock",
            "weather",
            "scores",
            "right now",
            "recent",
            "happening",
            "new",
            "trend",
            "trending",
            "live",
            "search",
            "find",
            "look up",
            "search for",
            "just happened",
            "what's going on",
            "who won",
            "what happened",
            "who is",
            "who are",
            "when is",
        ]
        return any(word in prompt.lower() for word in keywords)

    async def fetch_page_content(self, session, url: str, status_box=None, live=None) -> tuple[str, dict]:
        """Fetch HTML content of a page asynchronously."""
        domain = urlparse(url).netloc

        try:
            async with session.get(url, headers=self.headers, timeout=15) as response:
                if response.status != 200:
                    if status_box:
                        await status_box.log(f"🚫 {domain}: HTTP {response.status}", live)
                        live.update(status_box.render())

                    return "", {'is_accessible': False, 'issues': [f'HTTP {response.status}']}
                
                html = await response.text()
                
                # Assess content quality
                assessment = self.content_assessor.assess_html(html, url)
                
                if not assessment['is_accessible']:
                    await status_box.log(f"🚫 {domain}: {', '.join(assessment['issues'])}",live)
                    live.update(status_box.render())
                    return "", assessment
                
                if not assessment['is_quality']:
                    domain = urlparse(url).netloc
                    await status_box.log(f"⚠️ {domain}: low quality content", live)
                    live.update(status_box.render())
                    return "", assessment
                
                # Extract content
                doc = Document(html)
                content_html = doc.summary()
                soup = BeautifulSoup(content_html, 'html.parser')
                text_content = soup.get_text(separator='\n', strip=True)
                THRESHOLD_LENGTH = 3000 

                #print(text_content)
                if len(text_content) > THRESHOLD_LENGTH:
                    # Clean text using silent prompt
                    cleaning_prompt = [
                        {"role": "system", "content": (
                            "YOUR ONLY FUNCTION is to Clean and Format the following text. Remove noise, ads, "
                            "redundant spacing, and irrelevant content. Keep ALL dates, facts, and "
                            "important details. Format in clear paragraphs. RETURN ONLY the "
                            "cleaned text, no confirmation, explanations or markers."
                        )},
                        {"role": "user", "content": text_content}
                    ]
            
                    cleaned_text = await self.local_ai.query(
                        self.local_ai.messages_to_prompt(cleaning_prompt),
                        silent=True, silent_tokens =4096
                    )

                    # Limit content length
                    text_content = cleaned_text.strip()
                else:
                    text_content = text_content.strip()

                
                await status_box.log(f"  ✅ {domain}: {len(text_content)} chars extracted", live)
                live.update(status_box.render())
                await asyncio.sleep(0.2)
                
                return text_content, assessment
                
        except Exception as e:
            msg = f"❌ {domain}: {str(e)[:50]}"
            if status_box:
                await status_box.log(msg, live)
                live.update(status_box.render())
            return "", {'is_accessible': False, 'issues': [str(e)[:50]]}

    async def fetch_and_summarize_urls(self, urls: List[str]) -> str:
        status_box = StatusBox("🌍 searching Web...")

        """Fetch URLs with dynamic filtering and quality assessment"""
        with Live(status_box.render(), refresh_per_second=20, console=console) as live:
            await status_box.log(f"🔍 Analyzing {len(urls)} URLs...", live)
            live.update(status_box.render())
            await asyncio.sleep(1)
        
            # Stage 1: Pre-filter URLs by heuristics
            filtered = self.url_filter.filter_urls(urls, top_n=8)
        
            if not filtered:
                await status_box.log("⚠️ No quality URLs found in search results", live)
                live.update(status_box.render())
                await asyncio.sleep(2)
                return ""
        
            await status_box.log(f"\n📊 Top candidates:",live)
            for url, score, reason in filtered[:3]:
                domain = urlparse(url).netloc
                await status_box.log(f"  {score:2d} pts - {domain}: {reason}", live)
                live.update(status_box.render())
                await asyncio.sleep(.5)
        
            # Stage 2: Scrape and assess content quality
            await status_box.log(f"\n🌐 Fetching content from {len(filtered)} sources:", live)
            live.update(status_box.render())
            await asyncio.sleep(.5)
        
            async with aiohttp.ClientSession() as session:
                tasks = [self.fetch_page_content(session, url, status_box, live) for url, _, _ in filtered]
                results = await asyncio.gather(*tasks)
        
            # Collect successful content
            successful_content = []
            for (content, assessment), (url, score, reason) in zip(results, filtered):
                if content and assessment.get('is_quality'):
                    successful_content.append(content)
                    if len(successful_content) >= 5:  # Stop after 5 good sources
                        break
        
            if not successful_content:
                await status_box.log("\n💔 No accessible content found (paywalls/restrictions)", live)
                await asyncio.sleep(2)
                for _ in range(len(status_box.messages)):
                    await status_box.clear(live)
                    live.update(status_box.render())
                    await asyncio.sleep(0.02)
                # Clear box completely
                live.update("\n❌ no usable web content found.")
                return ""
            
        
            combined = "\n\n--- SOURCE ---\n\n".join(successful_content)
            await status_box.log(f"\n📖 Successfully retrieved {len(successful_content)} quality sources, summarizing...", live)
            live.update(status_box.render())
            await asyncio.sleep(2)

            # 💫 Animate shrink
            for _ in range(len(status_box.messages)):
                await status_box.clear(live)
                live.update(status_box.render())
                await asyncio.sleep(0.02)
            # Clear box completely
            live.update("\n✅ web retreaval done.")
            
            return combined.strip()
        
    async def ask(self, prompt: str) -> str:
        # Prepare the prompt for the model (instructions only)
        full_prompt = self.base_instruction

        # Include session memory as context
        # In ask()
        # Include summarized + recent session memory
        if self.session_memory:
            recent_memory =self.session_memory[-5:]  # last 5 exchanges
            full_memory = [
                f"\nUser: {m.get('prompt', m.get('user', ''))}\n\ncli-assist: {m.get('ai', '')}"
                for m in recent_memory
                if 'user' in m and 'ai' in m

            ]
            if full_memory:
                full_prompt += (
                    "\n\nConversation so, far context :\n"
                    + "\n".join(full_memory)
                )

        # --- Include online info if needed ---
        if self.should_search_online(prompt):
            search_results = self.search_manager.search(prompt)  # may return dicts or URLs
            if isinstance(search_results, str):
                search_results = search_results.splitlines()
            urls = []
            for line in search_results:
                line = line.strip()
                # match any http or https URL
                match = re.findall(r'https?://\S+', line)
                if match:
                    urls.extend(match)
            if urls:
                online_summaries = await self.fetch_and_summarize_urls(urls)
                if online_summaries:
                    full_prompt += f"\n\nALL of the following information is relevant, so to be included and organized, with dates, sources and important information whenever available, for your response to the User Prompt: \n\n{online_summaries}"

    
        # Add the user query at the end without echoing it in the output
        full_prompt += f"\n\n User prompt to be answered. It may diverge from the conversation, no need to suggest to get back on track or clarify anything in that case, just answer: \n\n{prompt}"
        # Query local model
        response = await self.local_ai.query(full_prompt)
        # Update memory
        await self.update_memory(prompt, response)

        # Strip whitespace and return only the model's answer
        return response.strip()

# Typing effect function
def type_out(text, prefix=""):
    print(prefix, end="", flush=True)
    for char in text:
        print(char, end="", flush=True)
        time.sleep(0.01) # adjust speed here
    print()  # newline after finishing
    
async def async_main():
    ai = cliassist()

    # First, select a session AFTER model is ready
    session = PromptSession()
    session_file = await select_session()
    await ai.load_session(session_file)    

    type_out("🔴 : cli-assist ready. type 'exit' or similar to quit.")

    while True:
        try:
            user_input = (await session.prompt_async(" \n> ")).strip()
            if user_input.lower() in ["exit", "quit", "bye"]:
                save_choice = await confirm_save_terminal()
                if save_choice:
                    await ai.save_session()
                    
                else:
                    type_out("🔴 : out of mind, out of sight. 🌅")
                break

            # Handle shell commands
            if user_input.startswith("!"):
                command = user_input[1:].strip()
                if command:
                    result = subprocess.run(command, shell=True, text=True, capture_output=True)
                    output = result.stdout or result.stderr
                    if output.strip():
                        type_out(output)
                continue  # don’t send this to AI

            await ai.ask(user_input)

        except (KeyboardInterrupt, EOFError):
            type_out("\n🌪️ : you messed me up bro, peace 🌅\n")
            break
    ai.local_ai.engine.shutdown()

def main():
    import asyncio
    asyncio.run(async_main())

if __name__ == "__main__":
    main()
