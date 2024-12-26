import discord
from discord.ext import commands
import asyncio
import config
import database
import utils
import logging

logger = logging.getLogger('evil_bot')

class CustomHelpCommand(commands.DefaultHelpCommand):
    def get_command_signature(self, command):
        return f"{config.COMMAND_PREFIX}{command.qualified_name}"
        
    async def send_bot_help(self, mapping):
        logger.debug("Generating bot help overview")
        ctx = self.context
        bot = ctx.bot
        filtered = await self.filter_commands(bot.commands, sort=True)
        em = discord.Embed(
            title="Evil Bot Commands", 
            description="Here are my evil commands! 😈",
            color=config.EMBED_COLOR
        )
        for command in filtered:
            name = self.get_command_signature(command)
            desc = command.brief or command.help.split('\n')[0] if command.help else "No description"
            em.add_field(name=name, value=desc, inline=False)
        await self.get_destination().send(embed=em)

    async def send_command_help(self, command):
        logger.debug(f"Generating help for command: {command.name}")
        em = discord.Embed(
            title=self.get_command_signature(command),
            description=command.help or "No detailed help available",
            color=config.EMBED_COLOR
        )
        await self.get_destination().send(embed=em)

class EvilBot(commands.Bot):
    def __init__(self):
        logger.info("Initializing EvilBot")
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix=config.COMMAND_PREFIX, 
            intents=intents,
            help_command=CustomHelpCommand()
        )
        self.setup_commands()
        logger.info("EvilBot initialization complete")

    async def on_ready(self):
        logger.info(f"{config.BOT_NAME} has risen! Logged in as {self.user}")
        database.init_db()

    def setup_commands(self):
        logger.info("Setting up bot commands")
        
        @self.command(
            name='set', 
            brief="Set my evil personality",
            help="Set a new system prompt to change my personality\n\nExample:\n!set You are Evil Bot, an AI assistant with evil tendencies"
        )
        async def set_prompt(ctx, *, prompt=None):
            logger.debug(f"Set command called by {ctx.author.id}")
            # Handle no prompt case
            if not prompt:
                logger.debug("No prompt provided, sending help message")
                await ctx.send(embed=utils.create_help_embed(
                    "Set Prompt",
                    "Set my evil personality!",
                    ["!set You are Evil Bot..."]
                ))
                return

            success = False
            if isinstance(ctx.channel, discord.DMChannel):
                logger.debug(f"Setting DM prompt for user {ctx.author.id}")
                success = database.set_dm_prompt(ctx.author.id, prompt)
            else:
                logger.debug(f"Attempting to set server prompt for {ctx.guild.id}")
                if not ctx.author.guild_permissions.administrator:
                    logger.warning(f"Permission denied for user {ctx.author.id}")
                    await ctx.send(embed=utils.no_permission_embed())
                    return
                success = database.set_server_prompt(ctx.guild.id, prompt)

            if success:
                logger.info("Prompt updated successfully")
                await ctx.send(embed=utils.create_embed(
                    "Personality Updated",
                    "*Evil laugh* I have updated my personality!",
                    [{'name': 'New Prompt', 'value': f"```{prompt}```"}]
                ))
            else:
                logger.error("Failed to update prompt")
                await ctx.send(embed=utils.error_embed(
                    "Error",
                    "Failed to update the system prompt!"
                ))

        @self.command(
            name='get',
            brief="Show my current evil personality",
            help="Display my current personality settings\n\nExample:\n!get"
        )
        async def get_prompt(ctx):
            logger.debug(f"Get command called by {ctx.author.id}")
            try:
                prompt = None
                if isinstance(ctx.channel, discord.DMChannel):
                    logger.debug(f"Getting DM prompt for user {ctx.author.id}")
                    prompt = database.get_dm_prompt(ctx.author.id)
                else:
                    logger.debug(f"Getting server prompt for {ctx.guild.id}")
                    prompt = database.get_server_prompt(ctx.guild.id)
                    
                await ctx.send(embed=utils.create_embed(
                    "Current Prompt",
                    "Here's how I'm currently configured to behave",
                    [{'name': 'Prompt', 'value': f"```{prompt}```"}]
                ))
            except Exception as e:
                logger.error(f"Error getting prompt: {e}", exc_info=True)
                await ctx.send(embed=utils.error_embed(
                    "Error",
                    "Failed to retrieve the system prompt!"
                ))

        @self.command(
            name='default',
            brief="Reset all settings to default",
            help="Reset all bot settings to their default values\n\nExample:\n!default"
        )
        async def default(ctx):
            logger.debug(f"Default command called by {ctx.author.id}")
            if isinstance(ctx.channel, discord.DMChannel):
                logger.debug(f"Resetting DM settings for user {ctx.author.id}")
                if database.set_dm_prompt(ctx.author.id, config.DEFAULT_PERSONA):
                    await ctx.send(embed=utils.create_embed(
                        "Settings Reset",
                        "Your DM settings have been reset to default! 😈"
                    ))
                else:
                    logger.error("Failed to reset DM settings")
                    await ctx.send(embed=utils.error_embed(
                        "Error",
                        "Failed to reset settings!"
                    ))
            else:
                logger.debug(f"Attempting to reset server settings for {ctx.guild.id}")
                if not ctx.author.guild_permissions.administrator:
                    logger.warning(f"Permission denied for user {ctx.author.id}")
                    await ctx.send(embed=utils.no_permission_embed())
                    return

                if database.reset_server_settings(ctx.guild.id):
                    logger.info("Server settings reset successfully")
                    await ctx.send(embed=utils.create_embed(
                        "Settings Reset",
                        "All settings have been reset to default values! 😈"
                    ))
                else:
                    logger.error("Failed to reset server settings")
                    await ctx.send(embed=utils.error_embed(
                        "Error",
                        "Failed to reset settings!"
                    ))

        @self.command(
            name='trigger',
            brief="Control what words summon me",
            help="Manage the words that make me respond\n\nExamples:\n!trigger list - Show all trigger words\n!trigger add evil overlord - Add a new trigger\n!trigger remove evil overlord - Remove a trigger"
        )
        async def trigger(ctx, action=None, *, word=None):
            logger.debug(f"Trigger command called by {ctx.author.id} with action: {action}")
            if isinstance(ctx.channel, discord.DMChannel):
                logger.debug("Trigger command used in DM, sending error")
                await ctx.send(embed=utils.error_embed(
                    "DM Not Supported",
                    "Trigger words can only be managed in servers!"
                ))
                return

            if not action:
                logger.debug("No action provided, sending help")
                await ctx.send(embed=utils.create_help_embed(
                    "Trigger Words",
                    "Manage words that make me respond",
                    ["!trigger list", "!trigger add evil overlord", "!trigger remove evil overlord"]
                ))
                return

            if not ctx.author.guild_permissions.administrator and action.lower() != 'list':
                logger.warning(f"Permission denied for user {ctx.author.id}")
                await ctx.send(embed=utils.no_permission_embed())
                return

            settings = database.get_server_settings(ctx.guild.id)
            if not settings:
                logger.error(f"Failed to get settings for server {ctx.guild.id}")
                await ctx.send(embed=utils.error_embed("Error", "Failed to get server settings!"))
                return

            action = action.lower()
            trigger_words = settings['trigger_words']

            if action == 'list':
                logger.debug("Listing trigger words")
                words_text = "\n".join([f"• {word}" for word in trigger_words]) or "No trigger words set!"
                await ctx.send(embed=utils.create_embed(
                    "Trigger Words",
                    "These words summon my evil presence!",
                    [{'name': "Current Triggers", 'value': words_text}]
                ))

            elif action == 'add' and word:
                logger.debug(f"Adding trigger word: {word}")
                if word.lower() in [w.lower() for w in trigger_words]:
                    await ctx.send(embed=utils.error_embed(
                        "Duplicate Trigger",
                        "That trigger word already exists!"
                    ))
                    return

                trigger_words.append(word.lower())
                if database.set_trigger_words(ctx.guild.id, trigger_words):
                    logger.info(f"Added trigger word: {word}")
                    await ctx.send(embed=utils.create_embed(
                        "Trigger Added",
                        f"Added new trigger word: `{word}`"
                    ))
                else:
                    logger.error("Failed to add trigger word")
                    await ctx.send(embed=utils.error_embed(
                        "Error",
                        "Failed to add trigger word!"
                    ))

            elif action == 'remove' and word:
                logger.debug(f"Removing trigger word: {word}")
                word_lower = word.lower()
                if word_lower not in [w.lower() for w in trigger_words]:
                    await ctx.send(embed=utils.error_embed(
                        "Unknown Trigger",
                        "That trigger word doesn't exist!"
                    ))
                    return

                trigger_words = [w for w in trigger_words if w.lower() != word_lower]
                if database.set_trigger_words(ctx.guild.id, trigger_words):
                    logger.info(f"Removed trigger word: {word}")
                    await ctx.send(embed=utils.create_embed(
                        "Trigger Removed",
                        f"Removed trigger word: `{word}`"
                    ))
                else:
                    logger.error("Failed to remove trigger word")
                    await ctx.send(embed=utils.error_embed(
                        "Error",
                        "Failed to remove trigger word!"
                    ))

            else:
                logger.debug("Invalid trigger command action")
                await ctx.send(embed=utils.create_help_embed(
                    "Invalid Action",
                    "Please use a valid action!",
                    ["!trigger list", "!trigger add <word>", "!trigger remove <word>"]
                ))

        @self.command(
            name='random',
            brief="Control my random evil appearances",
            help="Manage my random response settings\n\nExamples:\n!random status - Show current settings\n!random on - Enable random responses\n!random off - Disable random responses\n!random chance 20 - Set response chance to 20%"
        )
        async def random(ctx, action=None, chance: int = None):
            logger.debug(f"Random command called by {ctx.author.id} with action: {action}")
            if isinstance(ctx.channel, discord.DMChannel):
                logger.debug("Random command used in DM, sending error")
                await ctx.send(embed=utils.error_embed(
                    "DM Not Supported",
                    "Random responses can only be managed in servers!"
                ))
                return

            if not ctx.author.guild_permissions.administrator and action != 'status':
                logger.warning(f"Permission denied for user {ctx.author.id}")
                await ctx.send(embed=utils.no_permission_embed())
                return

            settings = database.get_server_settings(ctx.guild.id)
            if not settings:
                logger.error(f"Failed to get settings for server {ctx.guild.id}")
                await ctx.send(embed=utils.error_embed("Error", "Failed to get server settings!"))
                return

            if not action or action.lower() == 'status':
                logger.debug("Showing random response status")
                await ctx.send(embed=utils.create_embed(
                    "Random Response Settings",
                    None,
                    [
                        {'name': 'Status', 'value': "Enabled 😈" if settings['random_responses_enabled'] else "Disabled 🌑", 'inline': True},
                        {'name': 'Chance', 'value': f"{settings['random_response_chance']}%", 'inline': True}
                    ]
                ))
                return

            action = action.lower()
            if action == 'on':
                logger.debug("Enabling random responses")
                if database.set_random_responses(ctx.guild.id, True):
                    logger.info("Random responses enabled")
                    await ctx.send(embed=utils.create_embed("Random Responses Enabled"))
                else:
                    logger.error("Failed to enable random responses")
                    await ctx.send(embed=utils.error_embed("Error", "Failed to enable random responses!"))

            elif action == 'off':
                logger.debug("Disabling random responses")
                if database.set_random_responses(ctx.guild.id, False):
                    logger.info("Random responses disabled")
                    await ctx.send(embed=utils.create_embed("Random Responses Disabled"))
                else:
                    logger.error("Failed to disable random responses")
                    await ctx.send(embed=utils.error_embed("Error", "Failed to disable random responses!"))

            elif action == 'chance' and isinstance(chance, int):
                logger.debug(f"Setting random chance to {chance}%")
                if not 1 <= chance <= 100:
                    await ctx.send(embed=utils.create_help_embed(
                        "Invalid Chance",
                        "Chance must be between 1 and 100!",
                        ["!random chance 20"]
                    ))
                    return

                if database.set_random_chance(ctx.guild.id, chance):
                    logger.info(f"Random chance set to {chance}%")
                    await ctx.send(embed=utils.create_embed(
                        "Random Chance Updated",
                        f"Random response chance set to {chance}%!"
                    ))
                else:
                    logger.error("Failed to update random chance")
                    await ctx.send(embed=utils.error_embed("Error", "Failed to update random chance!"))

            else:
                logger.debug("Invalid random command action")
                await ctx.send(embed=utils.create_help_embed(
                    "Random Responses",
                    "Manage random response settings",
                    ["!random status", "!random on", "!random off", "!random chance 20"]
                ))

        logger.info("Command setup complete")

    async def on_message(self, message):
        logger.debug(f"Message received - Channel: {message.channel.id}, Author: {message.author.id}")
            
        if message.content.startswith(self.command_prefix):
            logger.info(f"Processing command: {message.content}")
            await self.process_commands(message)
            return
                
        if message.author.bot:
            logger.debug("Skipping bot message")
            return
                
        should_respond = False
        if isinstance(message.channel, discord.DMChannel):
            logger.debug("Message is in DM, should respond")
            should_respond = True
        else:
            logger.debug("Checking if should respond to server message")
            should_respond = utils.should_respond(message)
                
        if not should_respond:
            logger.debug("Decided not to respond to message")
            return

        logger.info(f"Preparing response to message: {message.clean_content[:50]}...")
        async with message.channel.typing():
            try:
                content = message.clean_content.replace(f'@{self.user.name}', '').strip()
                
                if isinstance(message.channel, discord.DMChannel):
                    logger.debug(f"Getting DM prompt for user {message.author.id}")
                    system_prompt = database.get_dm_prompt(message.author.id)
                else:
                    logger.debug(f"Getting server prompt for guild {message.guild.id}")
                    system_prompt = database.get_server_prompt(message.guild.id)
                
                context = [{'role': 'system', 'content': system_prompt}]
                
                if message.reference and message.reference.resolved:
                    logger.debug("Adding replied message to context")
                    replied_msg = message.reference.resolved
                    context.append({
                        'role': 'user' if replied_msg.author != self.user else 'assistant',
                        'content': replied_msg.clean_content
                    })
                
                logger.debug(f"Getting message history (max {config.MAX_CONTEXT_MESSAGES} messages)")
                async for hist_msg in message.channel.history(
                    limit=config.MAX_CONTEXT_MESSAGES,
                    before=message
                ):
                    if hist_msg.author.bot and hist_msg.author != self.user:
                        continue
                    context.append({
                        'role': 'user' if hist_msg.author != self.user else 'assistant',
                        'content': hist_msg.clean_content
                    })
                
                context.append({'role': 'user', 'content': content})

                try:
                    logger.debug(f"Getting response from Ollama using model {config.MODEL_NAME}")
                    response = await utils.get_ollama_response(context, config.MODEL_NAME)
                    response_content = response['message']['content']
                    logger.info("Successfully got response from Ollama")
                    logger.debug(f"Response content: {response_content[:100]}...")
                    await utils.split_and_send_message(message, response_content)
                except asyncio.TimeoutError:
                    logger.error("Ollama response timed out")
                    await message.reply("*Evil laugh fades* My dark powers are taking too long! Try again later. 😈")
                except Exception as e:
                    logger.error(f"Error getting response from Ollama: {e}", exc_info=True)
                    await message.reply("*Evil laugh turns into evil cough* Something went wrong with my dark powers! 😈")

            except Exception as e:
                logger.error(f"Error in message processing: {e}", exc_info=True)
                await message.reply("*Evil laugh turns into evil cough* Something went wrong with my dark powers! 😈")
