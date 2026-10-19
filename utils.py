import asyncio
import aiohttp
import ollama
import functools
import random
import discord
from concurrent.futures import ThreadPoolExecutor
import database
import config
import logging

logger = logging.getLogger('evil_bot')

# Single worker — Ollama calls must be sequential to avoid loading two models at once
thread_pool = ThreadPoolExecutor(max_workers=1)

# Lazily initialised — must not be created at import time on Python 3.9 because
# asyncio.Lock() binds to the running event loop and discord.py creates its own.
_model_lock = None  # type: asyncio.Lock

# In-memory cache for image descriptions, keyed by Discord attachment ID (snowflake).
# Evicts the oldest entry when the cap is reached (simple FIFO, good enough here).
_description_cache = {}
_DESCRIPTION_CACHE_MAX = 200

def _get_lock() -> asyncio.Lock:
    global _model_lock
    if _model_lock is None:
        _model_lock = asyncio.Lock()
    return _model_lock

def create_embed(title, description=None, fields=None, color=None):
    logger.debug(f"Creating embed - Title: {title}")
    em = discord.Embed(
        title=title,
        description=description,
        color=color if color is not None else config.EMBED_COLOR,
    )
    em.set_footer(text=config.BOT_NAME)
    em.timestamp = discord.utils.utcnow()
    if fields:
        for field in fields:
            em.add_field(
                name=field['name'],
                value=field['value'],
                inline=field.get('inline', False)
            )
    return em

def error_embed(title, description=None, fields=None):
    logger.debug(f"Creating error embed - Title: {title}")
    return create_embed(title, description, fields, color=config.EMBED_COLOR_ERROR)

def success_embed(title, description=None, fields=None):
    return create_embed(title, description, fields, color=config.EMBED_COLOR_SUCCESS)

def no_permission_embed():
    logger.debug("Creating permission denied embed")
    return error_embed("Permission Denied", "You don't have permission to use this command!")

# This function is just a bool that determines if the bot should respond or fuck off
def should_respond(message, bot_user):
    if message.author.bot:
        logger.debug("Skipping bot message")
        return False

    # The bot always responds to dms
    if isinstance(message.channel, discord.DMChannel):
        logger.debug("Message is in DM, should respond")
        return True

    # get the server settings
    settings = database.get_server_settings(message.guild.id)
    if not settings:
        logger.warning(f"No settings found for server {message.guild.id}")
        return False

    # If a channel whitelist is set, only respond in those channels
    whitelist = settings.get('channel_whitelist', [])
    if whitelist and message.channel.id not in whitelist:
        logger.debug("Channel not in whitelist, skipping")
        return False

    content_lower = message.content.lower()

    # if any trigger words are in the message, then respond
    triggered = any([
        bot_user in message.mentions,
        any(word in content_lower for word in settings['trigger_words']),
        message.reference and message.reference.resolved and
        message.reference.resolved.author == bot_user
    ])

    if triggered:
        logger.debug("Message triggered response")
        return True
        
    # Check and roll for random responses
    if settings['random_responses_enabled']:
        chance = random.randint(1, 100) <= settings['random_response_chance']
        if chance:
            logger.debug("Random response triggered")
        return chance
        
    return False

async def keep_typing(channel):
    """Keep the typing indicator alive for long Ollama responses."""
    try:
        while True:
            await channel.typing()
            await asyncio.sleep(8)
    except asyncio.CancelledError:
        pass

def resolve_mentions(content, guild):
    """Replace @name text in LLM output with real Discord mentions (<@id>)."""
    if not guild:
        return content
    # Sort longest names first to avoid partial matches (e.g. "Jo" inside "John")
    members = sorted(guild.members, key=lambda m: max(len(m.display_name), len(m.name)), reverse=True)
    for member in members:
        for name in [member.display_name, member.name]:
            placeholder = f'@{name}'
            if placeholder in content:
                content = content.replace(placeholder, f'<@{member.id}>')
                break
    logger.debug(f"Resolved mentions in response")
    return content

async def split_and_send_message(message, content):
    content = content.strip()
    if not content:
        logger.warning("Attempted to send empty message, skipping")
        return
    logger.debug(f"Splitting message of length {len(content)}")
    # This function splits really long messages because discords char limits suck
    if len(content) <= config.MAX_MESSAGE_LENGTH:
        await message.reply(content)
        return

    chunks = []
    while content:
        if len(content) <= config.MAX_MESSAGE_LENGTH:
            chunks.append(content)
            break

        split_index = content[:config.MAX_MESSAGE_LENGTH].rfind('.')
        if split_index == -1:
            split_index = content[:config.MAX_MESSAGE_LENGTH].rfind(' ')
            if split_index == -1:
                split_index = config.MAX_MESSAGE_LENGTH - 1

        chunks.append(content[:split_index + 1])
        content = content[split_index + 1:].strip()

    logger.debug(f"Split into {len(chunks)} chunks")
    first = True
    for chunk in chunks:
        if first:
            await message.reply(chunk)
            first = False
        else:
            await message.channel.send(chunk)

async def get_ollama_response(context, model_name):
    logger.debug(f"Getting Ollama response using model: {model_name}")
    loop = asyncio.get_running_loop()
    async with _get_lock():
        try:
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    thread_pool,
                    functools.partial(ollama.chat, model=model_name, messages=context)
                ),
                timeout=config.RESPONSE_TIMEOUT
            )
            logger.debug("Successfully got Ollama response")
            return response
        except asyncio.TimeoutError:
            logger.error("Ollama response timed out")
            raise
        except Exception as e:
            logger.error(f"Error getting Ollama response: {e}", exc_info=True)
            raise


async def describe_images(attachments, vision_model):
    """Download images and use the vision model to describe them.

    Checks the in-memory cache first so the same image is never described twice
    in a session. Uses keep_alive=0 so Ollama unloads the vision model from VRAM
    immediately after each call, freeing memory before the main model loads.
    """
    loop = asyncio.get_running_loop()
    descriptions = []
    async with aiohttp.ClientSession() as session:
        for attachment in attachments:
            # Return cached description if we've seen this attachment before
            if attachment.id in _description_cache:
                logger.debug(f"Cache hit for attachment {attachment.id} ({attachment.filename})")
                descriptions.append(_description_cache[attachment.id])
                continue

            try:
                async with session.get(attachment.url) as resp:
                    if resp.status != 200:
                        logger.warning(f"Failed to download image {attachment.url}: HTTP {resp.status}")
                        continue
                    image_bytes = await resp.read()

                logger.debug(f"Calling vision model '{vision_model}' for image: {attachment.filename}")
                async with _get_lock():
                    response = await asyncio.wait_for(
                        loop.run_in_executor(
                            thread_pool,
                            functools.partial(
                                ollama.chat,
                                model=vision_model,
                                messages=[{
                                    'role': 'user',
                                    'content': 'Describe this image concisely.',
                                    'images': [image_bytes],
                                }],
                                keep_alive=0,
                            )
                        ),
                        timeout=config.RESPONSE_TIMEOUT
                    )

                description = response['message']['content'].strip()
                logger.debug(f"Vision model described image: {description[:80]}...")
                entry = f'[Image description: {description}]'

                # Store in cache, evicting the oldest entry if we're at the cap
                if len(_description_cache) >= _DESCRIPTION_CACHE_MAX:
                    del _description_cache[next(iter(_description_cache))]
                _description_cache[attachment.id] = entry
                descriptions.append(entry)

            except asyncio.TimeoutError:
                logger.error(f"Vision model timed out on image: {attachment.filename}")
                descriptions.append(f'[Image: {attachment.filename} — vision model timed out]')
            except Exception as e:
                error_str = str(e).lower()
                if 'not found' in error_str or '404' in error_str or 'pull' in error_str:
                    logger.error(
                        f"Vision model '{vision_model}' not found in Ollama. "
                        f"Run: ollama pull {vision_model}"
                    )
                else:
                    logger.error(f"Vision model error on {attachment.filename}: {e}", exc_info=True)
                descriptions.append(f'[Image: {attachment.url}]')

    return '\n'.join(descriptions)
