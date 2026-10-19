# Evil Bot

A dark and mysterious Discord chatbot powered by local Ollama models.

## Prerequisites

- Python 3.9 or higher
- [Ollama](https://ollama.ai) running locally

## Setup

1. Install Ollama:
```bash
curl https://ollama.ai/install.sh | sh  # Linux/Mac
```

2. Pull the default model:
```bash
ollama pull dolphin-mixtral:8x7b
```

3. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate       # Linux/Mac
.\venv\Scripts\activate        # Windows
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Create a `.env` file in the project root. `BOT_TOKEN` is required; everything else is optional.

6. Run the bot:
```bash
python3 main.py
```

## Environment Variables

### Core

| Variable               | Description                                      | Default                       |
|------------------------|--------------------------------------------------|-------------------------------|
| `BOT_TOKEN`            | Discord bot token **(required)**                 | —                             |
| `BOT_NAME`             | Display name used in embed footers               | `Evil Bot`                    |
| `MODEL_NAME`           | Default Ollama model                             | `dolphin-mixtral:8x7b`        |
| `MAX_MESSAGE_LENGTH`   | Maximum Discord message length before splitting  | `2000`                        |
| `RESPONSE_TIMEOUT`     | Seconds to wait for an Ollama response           | `300`                         |
| `MAX_CONTEXT_MESSAGES` | Number of previous messages included in context  | `5`                           |

### Behaviour

| Variable                 | Description                                                         | Default                       |
|--------------------------|---------------------------------------------------------------------|-------------------------------|
| `DEFAULT_TRIGGER_WORDS`  | Comma-separated words that always trigger a response                | `evil,evil bot,good,good bot` |
| `DEFAULT_RANDOM_ENABLED` | Whether random responses are on by default                          | `True`                        |
| `DEFAULT_RANDOM_CHANCE`  | Default random response probability (1–100)                         | `10`                          |
| `DEFAULT_PERSONA`        | Default system prompt applied to new servers                        | See `config.py`               |

### Model switching

| Variable          | Description                                                                                    | Default |
|-------------------|------------------------------------------------------------------------------------------------|---------|
| `MODEL_WHITELIST` | Comma-separated list of Ollama models admins can switch to via `/model set`. Leave empty to disable model switching — only `MODEL_NAME` will be used. | *(empty — switching disabled)* |

**Example:**
```
MODEL_WHITELIST=llama3,mistral,gemma2,phi3
```

### Vision (image descriptions)

| Variable        | Description                                                                                     | Default     |
|-----------------|-------------------------------------------------------------------------------------------------|-------------|
| `VISION_ENABLED` | Enable the two-step vision pipeline. When on, images are described by `VISION_MODEL` and the description is injected into context before the main model responds. | `False`     |
| `VISION_MODEL`  | Ollama vision model used to describe images. Must be pulled separately.                         | `moondream` |

**Example:**
```
VISION_ENABLED=True
VISION_MODEL=moondream
```
Then pull the vision model: `ollama pull moondream`

### Embeds

| Variable             | Description                          | Default     |
|----------------------|--------------------------------------|-------------|
| `EMBED_COLOR`        | Left-bar colour for info embeds      | `0x2b2d31`  |
| `EMBED_COLOR_ERROR`  | Left-bar colour for error embeds     | `0xd32f2f`  |
| `EMBED_COLOR_SUCCESS`| Left-bar colour for success embeds   | `0x43b581`  |

### Database & logging

| Variable             | Description                                                           | Default          |
|----------------------|-----------------------------------------------------------------------|------------------|
| `DATABASE_NAME`      | SQLite database file path                                             | `bot_settings.db`|
| `MAX_PROMPT_HISTORY` | Maximum prompt history entries kept per server (oldest are pruned)    | `50`             |
| `LOG_FILE_NAME`      | Log file name (written inside `logs/`)                                | `bot.log`        |
| `LOG_MAX_SIZE`       | Total log capacity in bytes across all rotated files                  | `536870912` (0.5 GB) |
| `LOG_BACKUP_COUNT`   | Number of rotated log files to keep                                   | `4`              |

## Commands

All commands use Discord slash commands (`/`).

### Personality

| Command | Permission | Description |
|---------|-----------|-------------|
| `/set <prompt>` | Admin (server) / Anyone (DM) | Set the bot's system prompt |
| `/get` | Anyone | Show the current system prompt |
| `/default` | Admin | Reset all settings to defaults |
| `/status` | Anyone | Show all current server settings |

### Prompt history

| Command | Permission | Description |
|---------|-----------|-------------|
| `/history list` | Admin | Show the last 10 system prompts |
| `/history load <id>` | Admin | Restore a past system prompt by ID |

### Presets

| Command | Permission | Description |
|---------|-----------|-------------|
| `/preset list` | Anyone | List saved personality presets |
| `/preset save <name>` | Admin | Save the current personality as a named preset |
| `/preset load <name>` | Admin | Load a saved preset as the active personality |
| `/preset delete <name>` | Admin | Delete a saved preset |

### Trigger words

| Command | Permission | Description |
|---------|-----------|-------------|
| `/trigger list` | Anyone | Show all trigger words |
| `/trigger add <word>` | Admin | Add a trigger word |
| `/trigger remove <word>` | Admin | Remove a trigger word |

### Random responses

| Command | Permission | Description |
|---------|-----------|-------------|
| `/random status` | Anyone | Show current random response settings |
| `/random on` | Admin | Enable random responses |
| `/random off` | Admin | Disable random responses |
| `/random chance <1-100>` | Admin | Set the random response probability |

### Channel restrictions

| Command | Permission | Description |
|---------|-----------|-------------|
| `/channel list` | Anyone | Show whitelisted channels (empty = all) |
| `/channel add <channel>` | Admin | Restrict responses to a specific channel |
| `/channel remove <channel>` | Admin | Remove a channel from the whitelist |
| `/channel clear` | Admin | Remove all restrictions — respond everywhere |

### Model switching

Requires `MODEL_WHITELIST` to be configured.

| Command | Permission | Description |
|---------|-----------|-------------|
| `/model list` | Anyone | Show available models and the active one |
| `/model set <model>` | Admin | Switch to a different model |
| `/model reset` | Admin | Revert to the default model |
