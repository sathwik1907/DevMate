# DevMate - AI Developer Companion

DevMate is a Streamlit hackathon project that gives developers an AI companion with short-term chat history, long-term memory, code review, bug explanation, README generation, commit message generation, learning notes, and project memory.

OpenRouter performs reasoning through the OpenAI-compatible `https://openrouter.ai/api/v1` endpoint. Cognee provides persistent memory.

## Features

- AI chat with Markdown and code block rendering
- Context-aware answers using relevant Cognee memories
- Persistent developer memories such as name, editor, language, and project goals
- Memory recall for questions like "What editor do I use?"
- Code review for pasted source code
- Bug fix assistant for tracebacks and error reports
- Professional README.md generator
- Git commit message generator
- Learning notes stored in Cognee
- Project memory for progress, future tasks, and completed features
- Session chat history in Streamlit
- Modern sidebar, tabs, status indicators, spinners, and success/error states
- Graceful handling for empty prompts, missing keys, model errors, Cognee failures, and network issues

## Tech Stack

- Python
- Streamlit
- Cognee
- OpenRouter
- OpenAI Python SDK for OpenRouter's OpenAI-compatible API
- FastEmbed for Cognee embeddings
- python-dotenv

## Architecture

```text
app.py
  Streamlit UI, session state, tabs, forms, status indicators

llm.py
  OpenRouter client, free-model fallback, prompt assembly, feature-specific generation helpers

memory.py
  Cognee remember/recall wrapper, OpenRouter-compatible Cognee config, async safety

prompts.py
  Prompt templates for chat, code review, bug fixing, README generation, and commits
```

Request flow:

```text
User input -> Cognee recall -> OpenRouter prompt with memory -> OpenRouter response -> Streamlit UI
```

Memory flow:

```text
Saved note/progress/profile -> Cognee remember -> Cognee recall -> injected into OpenRouter context
```

## Get An OpenRouter API Key

1. Go to `https://openrouter.ai`.
2. Sign in or create an account.
3. Open Keys in your OpenRouter dashboard.
4. Create an API key.
5. Add it to `.env` as `OPENROUTER_API_KEY`.

## Installation

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Setup

Copy the example environment file:

```bash
cp .env.example .env
```

Then add your key:

```env
OPENROUTER_API_KEY=your_openrouter_api_key
LLM_API_KEY=your_openrouter_api_key
```

The full configuration is:

```env
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_MODEL=poolside/laguna-xs-2.1:free
OPENROUTER_FALLBACK_MODELS=cohere/north-mini-code:free,qwen/qwen3-next-80b-a3b-instruct:free,openai/gpt-oss-120b:free
OPENROUTER_MAX_TOKENS=4096
OPENROUTER_TIMEOUT_SECONDS=30
OPENROUTER_TEMPERATURE=0.2
OPENROUTER_TOP_P=0.9
OPENROUTER_SITE_URL=http://localhost:8501
OPENROUTER_APP_NAME=DevMate

COGNEE_SKIP_CONNECTION_TEST=true
LLM_PROVIDER=openai
LLM_MODEL=openai/poolside/laguna-xs-2.1:free
LLM_ENDPOINT=https://openrouter.ai/api/v1
LLM_API_KEY=your_openrouter_api_key
EMBEDDING_PROVIDER=fastembed
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
COGNEE_DATASET_NAME=devmate_openrouter_memory
COGNEE_SESSION_ID=devmate-default-session
COGNEE_TOP_K=8
COGNEE_PERMANENT_MEMORY=true
```

`llm.py` calls OpenRouter directly through the OpenAI Python SDK. On startup, it queries `https://openrouter.ai/api/v1/models`, filters for currently listed free text chat models, and automatically falls back across valid free models if one provider is unavailable. `memory.py` keeps Cognee compatible by using Cognee's `openai` provider internally, pointing `LLM_ENDPOINT` to OpenRouter, and mapping `OPENROUTER_API_KEY` into `LLM_API_KEY` at runtime.

## How To Run

```bash
streamlit run app.py
```

Open the local Streamlit URL shown in the terminal.

## Screenshots

Add final judging screenshots here:

- `assets/chat.png`
- `assets/memory.png`
- `assets/code-review.png`
- `assets/project-memory.png`

## Usage

1. Open the Memory tab and save facts like "My name is Sathwik" or "I use VS Code."
2. Ask the Chat tab "What is my name?" or "What editor do I use?"
3. Paste code into Code Review for explanation, bug detection, and improvements.
4. Paste a traceback into Bug Fix for root cause and repair steps.
5. Save learning notes and project progress in Notes & Project.
6. Generate README and commit message drafts from project descriptions or diffs.

## Error Handling

DevMate avoids hard crashes by handling:

- Missing `OPENROUTER_API_KEY`
- Model failures with automatic fallback to another free model
- API timeouts and network failures
- Rate limits with exponential backoff
- Empty model responses
- Cognee save/recall failures
- Empty prompts and empty form submissions
- Streamlit session state resets

OpenRouter failures return a user-friendly message in the app, such as:

```text
OpenRouter is temporarily unavailable: <actual error>
```

## Future Work

- Add authentication for multiple developers
- Add repository diff ingestion for richer commit messages
- Add export/import for saved Cognee memory collections
- Add screenshot assets for the final demo
- Add automated UI tests for each Streamlit tab
# DevMate
