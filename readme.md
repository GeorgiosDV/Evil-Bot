# Evil Bot

A dark and mysterious Discord chatbot tasked with spreading mischief powered by Ollama.

## Prerequisites

- SQLite3 
- Python 3.8 or higher

## Setup

1. Install [Ollama](https://ollama.ai):
```bash
curl https://ollama.ai/install.sh | sh  # On Linux/Mac
```

2. Pull the default model:
```bash
ollama pull dolphin-mixtral:8x7b
```

3. Create and activate virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Linux/Mac
# or
.\venv\Scripts\activate  # On Windows
```

4. Install Python dependencies:
```bash
pip install -r requirements.txt
```

5. Create a `.env` file in the project's root directory.
   - The `BOT_TOKEN` must be specified.

6. Run the bot:
```bash
python3 main.py
```

## Environment Variables

| Variable                 | Description                              | Default                       |
|--------------------------|------------------------------------------|-------------------------------|
| `BOT_TOKEN`              | Your bot token (Required)                | None                          |
| `BOT_NAME`               | Name of the bot                          | "Evil Bot"                    |
| `COMMAND_PREFIX`         | Command prefix                           | "!"                           |
| `MODEL_NAME`             | Ollama model                             | "dolphin-mixtral:8x7b"        |
| `MAX_MESSAGE_LENGTH`     | Max Discord message length               | 2000                          |
| `EMBED_COLOR`            | Discord embeds color                     | "0x800000"                    |
| `RESPONSE_TIMEOUT`       | Responses Timeout                        | 300                           |
| `MAX_CONTEXT_MESSAGES`   | Max number of messages in context window | 5                             |
| `DEFAULT_TRIGGER_WORDS`  | Comma-separated list of trigger words    | "evil,evil bot,good,good bot" |
| `DEFAULT_RANDOM_ENABLED` | Default random responses boolean         | "True"                        |
| `DEFAULT_RANDOM_CHANCE`  | Default random responses percentage      | 10                            |
| `DEFAULT_PERSONA`        | Default system prompt                    | See config.py                 |
| `DATABASE_NAME`          | SQLite database file                     | "bot_settings.db"             |
| `LOG_FILE_NAME`          | Log file                                 | "bot.log"                     |
| `LOG_MAX_SIZE`           | Maximum size of log files in bytes       | 5GB                           |
| `LOG_BACKUP_COUNT`       | Number of backup log files to keep       | 4                             |

## Commands

- `!set` - Set the bot's personality/system prompt
- `!get` - Show current personality settings
- `!default` - Reset all settings to default
- `!trigger` - Manage trigger words
- `!random` - Control random response settings
- `!help` - Show all available commands
