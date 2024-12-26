import asyncio
import ollama
import functools
import random
import discord
from concurrent.futures import ThreadPoolExecutor
import database
import config
import logging

logger = logging.getLogger('evil_bot')

# create a thread pool for ollama, i just chose 2 threads cause I don't really need more
thread_pool = ThreadPoolExecutor(max_workers=2)

def create_embed(title, description=None, fields=None, error=False):
    logger.debug(f"Creating embed - Title: {title}, Error: {error}")
    emoji = "🌑" if error else "😈"
    em = discord.Embed(
        title=f"{title} {emoji}",
        description=description,
        color=config.EMBED_COLOR
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
        "You don't have permission to use this command!"
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

# This function is just a bool that determines if the bot should respond or fuck off
def should_respond(message):
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
        
    content_lower = message.content.lower()
    
    # if any trigger words are in the message, then respond
    triggered = any([
        message.mentions and any(user.bot for user in message.mentions),
        any(word in content_lower for word in settings['trigger_words']),
        message.reference and message.reference.resolved and 
        message.reference.resolved.author.bot
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

async def split_and_send_message(message, content):
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
    loop = asyncio.get_event_loop()
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
