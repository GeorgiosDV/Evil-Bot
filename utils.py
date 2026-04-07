import asyncio
import ollama
import functools
import random
import discord
from concurrent.futures import ThreadPoolExecutor
import config
import logging

logger = logging.getLogger('evil_bot')

# Create a thread pool for ollama calls
thread_pool = ThreadPoolExecutor(max_workers=2)

def create_embed(title, description=None, fields=None, error=False):
    logger.debug(f"Creating embed - Title: {title}, Error: {error}")
    em = discord.Embed(
        title=title,
        description=description,
        color=config.ERROR_EMBED_COLOR if error else config.EMBED_COLOR
    )
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
    return create_embed(title, description, fields, error=True)

def no_permission_embed():
    logger.debug("Creating permission denied embed")
    return error_embed(
        "Permission Denied",
        "You don't have permission to use this command."
    )

def create_help_embed(command_name, description, examples=None, fields=None):
    logger.debug(f"Creating help embed for command: {command_name}")
    em = create_embed(f"Help: {command_name}", description)
    if examples:
        examples_text = "\n".join([f"• `{ex}`" for ex in examples])
        em.add_field(name="Examples", value=examples_text, inline=False)
    if fields:
        for field in fields:
            em.add_field(**field)
    return em

def should_respond(message, bot_user, settings):
    content_lower = message.content.lower()

    triggered = any([
        bot_user in message.mentions,
        any(word in content_lower for word in settings['trigger_words']),
        message.reference and message.reference.resolved and
        message.reference.resolved.author == bot_user
    ])

    if triggered:
        logger.debug("Message triggered response")
        return True

    if settings['random_responses_enabled']:
        chance = random.randint(1, 100) <= settings['random_response_chance']
        if chance:
            logger.debug("Random response triggered")
        return chance

    return False

async def split_and_send_message(message, content):
    logger.debug(f"Splitting message of length {len(content)}")
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
