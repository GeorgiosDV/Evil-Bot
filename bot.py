import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import config
import database
import utils
import logging

logger = logging.getLogger('evil_bot')


class EvilBot(commands.Bot):
    def __init__(self):
        logger.info("Initializing EvilBot")
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix='\x00', intents=intents)
        self._register_commands()
        logger.info("EvilBot initialization complete")

    async def setup_hook(self):
        database.init_db()
        await self.tree.sync()
        logger.info("Slash commands synced globally")

    async def on_ready(self):
        logger.info(f"{config.BOT_NAME} has risen! Logged in as {self.user}")
        for guild in self.guilds:
            database.get_server_settings(guild.id)

    async def on_guild_join(self, guild):
        logger.info(f"Joined new guild: {guild.id} ({guild.name})")
        database.get_server_settings(guild.id)

    async def on_message(self, message):
        logger.debug(f"Message received - Channel: {message.channel.id}, Author: {message.author.id}")

        if message.author.bot:
            return

        should_respond = False
        if isinstance(message.channel, discord.DMChannel):
            should_respond = True
        else:
            should_respond = utils.should_respond(message, self.user)

        if not should_respond:
            return

        logger.info(f"Preparing response to message: {message.clean_content[:50]}...")
        typing_task = asyncio.create_task(utils.keep_typing(message.channel))
        try:
            bot_display_name = message.guild.me.display_name if message.guild else self.user.display_name
            content = message.clean_content.replace(f'@{bot_display_name}', '').strip()

            # Image handling — two-step pipeline when VISION_ENABLED:
            # 1. vision model describes the image (keep_alive=0 → unloads from VRAM)
            # 2. description injected into context for the main model
            images = [
                a for a in message.attachments
                if (a.content_type and a.content_type.startswith('image/'))
                or a.filename.lower().endswith('.gif')
            ]
            if images:
                if config.VISION_ENABLED:
                    logger.debug(f"OCR enabled — describing {len(images)} image(s) with vision model")
                    descriptions = await utils.describe_images(images, config.VISION_MODEL)
                    if descriptions:
                        content = f"{content}\n{descriptions}".strip()
                else:
                    image_note = '\n'.join(f'[Image: {a.url}]' for a in images)
                    content = f"{content}\n{image_note}".strip()

            if isinstance(message.channel, discord.DMChannel):
                system_prompt = database.get_dm_prompt(message.author.id)
                model_name = config.MODEL_NAME
            else:
                system_prompt = database.get_server_prompt(message.guild.id)
                model_name = database.get_server_model(message.guild.id)

            context = [{'role': 'system', 'content': system_prompt}]

            if message.reference and message.reference.resolved:
                replied_msg = message.reference.resolved
                context.append({
                    'role': 'user' if replied_msg.author != self.user else 'assistant',
                    'content': replied_msg.clean_content,
                })

            history = []
            async for hist_msg in message.channel.history(limit=config.MAX_CONTEXT_MESSAGES, before=message):
                if hist_msg.author.bot and hist_msg.author != self.user:
                    continue
                history.append({
                    'role': 'user' if hist_msg.author != self.user else 'assistant',
                    'content': hist_msg.clean_content,
                })
            context.extend(reversed(history))
            context.append({'role': 'user', 'content': content})

            try:
                logger.debug(f"Getting response from Ollama using model {model_name}")
                response = await utils.get_ollama_response(context, model_name)
                response_content = response['message']['content']
                response_content = utils.resolve_mentions(response_content, message.guild)
                await utils.split_and_send_message(message, response_content)
            except asyncio.TimeoutError:
                logger.error("Ollama response timed out")
                await message.reply(
                    f"Response timed out after {config.RESPONSE_TIMEOUT}s. "
                    "Ollama may be overloaded — try again shortly."
                )
            except Exception as e:
                logger.error(f"Error getting Ollama response: {e}", exc_info=True)
                error_str = str(e).lower()
                if 'connection refused' in error_str or 'cannot connect' in error_str or 'connectorerror' in error_str:
                    await message.reply("Can't reach Ollama — is it running? (`ollama serve`)")
                elif 'not found' in error_str or '404' in error_str or 'pull' in error_str:
                    await message.reply(
                        f"Model `{model_name}` wasn't found in Ollama. "
                        f"Run: `ollama pull {model_name}`"
                    )
                else:
                    await message.reply(f"Ollama error: {str(e)[:300]}")

        except Exception as e:
            logger.error(f"Error in message processing: {e}", exc_info=True)
            await message.reply(f"Failed to process message: {str(e)[:300]}")
        finally:
            typing_task.cancel()
            try:
                await typing_task
            except asyncio.CancelledError:
                pass

    def _register_commands(self):

        # ── /set ──────────────────────────────────────────────────────────────
        @self.tree.command(name="set", description="Set my personality (server: admin only)")
        @app_commands.describe(prompt="The system prompt / personality to use")
        async def set_cmd(interaction: discord.Interaction, prompt: str):
            logger.debug(f"/set called by {interaction.user.id}")
            if interaction.guild is None:
                success = database.set_dm_prompt(interaction.user.id, prompt)
            else:
                if not interaction.user.guild_permissions.administrator:
                    await interaction.response.send_message(embed=utils.no_permission_embed(), ephemeral=True)
                    return
                success = database.set_server_prompt(interaction.guild.id, prompt)
                if success:
                    database.add_prompt_history(interaction.guild.id, prompt, interaction.user.id)
            if success:
                await interaction.response.send_message(embed=utils.success_embed(
                    "Personality Updated",
                    "Personality has been updated.",
                    [{'name': 'New Prompt', 'value': f"```{prompt[:900]}```"}],
                ))
            else:
                await interaction.response.send_message(
                    embed=utils.error_embed("Error", "Failed to update the system prompt!"), ephemeral=True
                )

        # ── /get ──────────────────────────────────────────────────────────────
        @self.tree.command(name="get", description="Show my current personality")
        async def get_cmd(interaction: discord.Interaction):
            logger.debug(f"/get called by {interaction.user.id}")
            try:
                if interaction.guild is None:
                    prompt = database.get_dm_prompt(interaction.user.id)
                else:
                    prompt = database.get_server_prompt(interaction.guild.id)
                await interaction.response.send_message(embed=utils.create_embed(
                    "Current Prompt",
                    "Here's how I'm currently configured",
                    [{'name': 'Prompt', 'value': f"```{prompt[:900]}```"}],
                ), ephemeral=True)
            except Exception as e:
                logger.error(f"Error in /get: {e}", exc_info=True)
                await interaction.response.send_message(
                    embed=utils.error_embed("Error", "Failed to retrieve the system prompt!"), ephemeral=True
                )

        # ── /default ──────────────────────────────────────────────────────────
        @self.tree.command(name="default", description="Reset all settings to default (server: admin only)")
        async def default_cmd(interaction: discord.Interaction):
            logger.debug(f"/default called by {interaction.user.id}")
            if interaction.guild is None:
                success = database.set_dm_prompt(interaction.user.id, config.DEFAULT_PERSONA)
                msg = "Your DM settings have been reset to default!"
            else:
                if not interaction.user.guild_permissions.administrator:
                    await interaction.response.send_message(embed=utils.no_permission_embed(), ephemeral=True)
                    return
                success = database.reset_server_settings(interaction.guild.id)
                msg = "All server settings have been reset to default!"
            if success:
                await interaction.response.send_message(embed=utils.success_embed("Settings Reset", msg))
            else:
                await interaction.response.send_message(
                    embed=utils.error_embed("Error", "Failed to reset settings!"), ephemeral=True
                )

        # ── /status ───────────────────────────────────────────────────────────
        @self.tree.command(name="status", description="Show all current bot settings")
        async def status_cmd(interaction: discord.Interaction):
            logger.debug(f"/status called by {interaction.user.id}")
            if interaction.guild is None:
                prompt = database.get_dm_prompt(interaction.user.id)
                await interaction.response.send_message(embed=utils.create_embed(
                    "DM Settings", None,
                    [{'name': 'Prompt', 'value': f"```{prompt[:900]}```"}],
                ), ephemeral=True)
                return
            settings = database.get_server_settings(interaction.guild.id)
            if not settings:
                await interaction.response.send_message(
                    embed=utils.error_embed("Error", "Failed to get server settings!"), ephemeral=True
                )
                return
            whitelist = settings['channel_whitelist']
            channel_text = ' '.join(f'<#{cid}>' for cid in whitelist) if whitelist else "All channels"
            words_text = ', '.join(f'`{w}`' for w in settings['trigger_words']) if settings['trigger_words'] else "None"
            await interaction.response.send_message(embed=utils.create_embed(
                "Server Settings", None,
                [
                    {'name': 'Prompt', 'value': f"```{settings['system_prompt'][:400]}```", 'inline': False},
                    {'name': 'Model', 'value': f"`{settings['model_name'] or config.MODEL_NAME}`", 'inline': True},
                    {'name': 'Random Responses', 'value': f"{'Enabled' if settings['random_responses_enabled'] else 'Disabled'} ({settings['random_response_chance']}%)", 'inline': True},
                    {'name': 'Trigger Words', 'value': words_text, 'inline': False},
                    {'name': 'Active Channels', 'value': channel_text, 'inline': False},
                ],
            ), ephemeral=True)

        # ── /trigger ──────────────────────────────────────────────────────────
        trigger_group = app_commands.Group(name="trigger", description="Manage words that make me respond")

        @trigger_group.command(name="list", description="Show all trigger words")
        async def trigger_list(interaction: discord.Interaction):
            if interaction.guild is None:
                await interaction.response.send_message(embed=utils.error_embed("Server Only", "Trigger words only work in servers!"), ephemeral=True)
                return
            settings = database.get_server_settings(interaction.guild.id)
            words_text = '\n'.join(f'• {w}' for w in settings['trigger_words']) if settings and settings['trigger_words'] else "No trigger words set!"
            await interaction.response.send_message(embed=utils.create_embed(
                "Trigger Words", "These words summon my evil presence!",
                [{'name': "Current Triggers", 'value': words_text}],
            ))

        @trigger_group.command(name="add", description="Add a trigger word (admin only)")
        @app_commands.describe(word="Word or phrase to add")
        async def trigger_add(interaction: discord.Interaction, word: str):
            if interaction.guild is None:
                await interaction.response.send_message(embed=utils.error_embed("Server Only", "Trigger words only work in servers!"), ephemeral=True)
                return
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(embed=utils.no_permission_embed(), ephemeral=True)
                return
            settings = database.get_server_settings(interaction.guild.id)
            words = settings['trigger_words']
            if word.lower() in [w.lower() for w in words]:
                await interaction.response.send_message(embed=utils.error_embed("Duplicate", "That trigger word already exists!"), ephemeral=True)
                return
            words.append(word.lower())
            if database.set_trigger_words(interaction.guild.id, words):
                await interaction.response.send_message(embed=utils.success_embed("Trigger Added", f"Added trigger word: `{word}`"))
            else:
                await interaction.response.send_message(embed=utils.error_embed("Error", "Failed to add trigger word!"), ephemeral=True)

        @trigger_group.command(name="remove", description="Remove a trigger word (admin only)")
        @app_commands.describe(word="Word or phrase to remove")
        async def trigger_remove(interaction: discord.Interaction, word: str):
            if interaction.guild is None:
                await interaction.response.send_message(embed=utils.error_embed("Server Only", "Trigger words only work in servers!"), ephemeral=True)
                return
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(embed=utils.no_permission_embed(), ephemeral=True)
                return
            settings = database.get_server_settings(interaction.guild.id)
            words = settings['trigger_words']
            word_lower = word.lower()
            if word_lower not in [w.lower() for w in words]:
                await interaction.response.send_message(embed=utils.error_embed("Not Found", "That trigger word doesn't exist!"), ephemeral=True)
                return
            words = [w for w in words if w.lower() != word_lower]
            if database.set_trigger_words(interaction.guild.id, words):
                await interaction.response.send_message(embed=utils.success_embed("Trigger Removed", f"Removed trigger word: `{word}`"))
            else:
                await interaction.response.send_message(embed=utils.error_embed("Error", "Failed to remove trigger word!"), ephemeral=True)

        self.tree.add_command(trigger_group)

        # ── /random ───────────────────────────────────────────────────────────
        random_group = app_commands.Group(name="random", description="Control random response behavior")

        @random_group.command(name="status", description="Show current random response settings")
        async def random_status(interaction: discord.Interaction):
            if interaction.guild is None:
                await interaction.response.send_message(embed=utils.error_embed("Server Only", "Random responses only work in servers!"), ephemeral=True)
                return
            settings = database.get_server_settings(interaction.guild.id)
            await interaction.response.send_message(embed=utils.create_embed("Random Responses", None, [
                {'name': 'Status', 'value': "Enabled 😈" if settings['random_responses_enabled'] else "Disabled 🌑", 'inline': True},
                {'name': 'Chance', 'value': f"{settings['random_response_chance']}%", 'inline': True},
            ]))

        @random_group.command(name="on", description="Enable random responses (admin only)")
        async def random_on(interaction: discord.Interaction):
            if interaction.guild is None:
                await interaction.response.send_message(embed=utils.error_embed("Server Only", "Random responses only work in servers!"), ephemeral=True)
                return
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(embed=utils.no_permission_embed(), ephemeral=True)
                return
            if database.set_random_responses(interaction.guild.id, True):
                await interaction.response.send_message(embed=utils.success_embed("Random Responses Enabled", "I'll now randomly chime in."))
            else:
                await interaction.response.send_message(embed=utils.error_embed("Error", "Failed to enable random responses!"), ephemeral=True)

        @random_group.command(name="off", description="Disable random responses (admin only)")
        async def random_off(interaction: discord.Interaction):
            if interaction.guild is None:
                await interaction.response.send_message(embed=utils.error_embed("Server Only", "Random responses only work in servers!"), ephemeral=True)
                return
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(embed=utils.no_permission_embed(), ephemeral=True)
                return
            if database.set_random_responses(interaction.guild.id, False):
                await interaction.response.send_message(embed=utils.success_embed("Random Responses Disabled", "I'll stay quiet unless summoned."))
            else:
                await interaction.response.send_message(embed=utils.error_embed("Error", "Failed to disable random responses!"), ephemeral=True)

        @random_group.command(name="chance", description="Set random response probability (admin only)")
        @app_commands.describe(percent="Response chance from 1 to 100")
        async def random_chance(interaction: discord.Interaction, percent: int):
            if interaction.guild is None:
                await interaction.response.send_message(embed=utils.error_embed("Server Only", "Random responses only work in servers!"), ephemeral=True)
                return
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(embed=utils.no_permission_embed(), ephemeral=True)
                return
            if not 1 <= percent <= 100:
                await interaction.response.send_message(embed=utils.error_embed("Invalid Value", "Chance must be between 1 and 100!"), ephemeral=True)
                return
            if database.set_random_chance(interaction.guild.id, percent):
                await interaction.response.send_message(embed=utils.success_embed("Chance Updated", f"Random response chance set to {percent}%."))
            else:
                await interaction.response.send_message(embed=utils.error_embed("Error", "Failed to update chance!"), ephemeral=True)

        self.tree.add_command(random_group)

        # ── /channel ──────────────────────────────────────────────────────────
        channel_group = app_commands.Group(name="channel", description="Control which channels I respond in")

        @channel_group.command(name="list", description="Show whitelisted channels (empty = all channels)")
        async def channel_list(interaction: discord.Interaction):
            if interaction.guild is None:
                await interaction.response.send_message(embed=utils.error_embed("Server Only", "Channel settings only work in servers!"), ephemeral=True)
                return
            settings = database.get_server_settings(interaction.guild.id)
            whitelist = settings['channel_whitelist']
            text = ' '.join(f'<#{cid}>' for cid in whitelist) if whitelist else "Responding in all channels."
            await interaction.response.send_message(embed=utils.create_embed("Active Channels", text))

        @channel_group.command(name="add", description="Restrict me to a specific channel (admin only)")
        @app_commands.describe(channel="Channel to add to the whitelist")
        async def channel_add(interaction: discord.Interaction, channel: discord.TextChannel):
            if interaction.guild is None:
                await interaction.response.send_message(embed=utils.error_embed("Server Only", "Channel settings only work in servers!"), ephemeral=True)
                return
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(embed=utils.no_permission_embed(), ephemeral=True)
                return
            settings = database.get_server_settings(interaction.guild.id)
            whitelist = settings['channel_whitelist']
            if channel.id in whitelist:
                await interaction.response.send_message(embed=utils.error_embed("Already Added", "That channel is already in the list!"), ephemeral=True)
                return
            whitelist.append(channel.id)
            if database.set_channel_whitelist(interaction.guild.id, whitelist):
                await interaction.response.send_message(embed=utils.success_embed("Channel Added", f"Now responding in {channel.mention}."))
            else:
                await interaction.response.send_message(embed=utils.error_embed("Error", "Failed to update channel list!"), ephemeral=True)

        @channel_group.command(name="remove", description="Remove a channel from the whitelist (admin only)")
        @app_commands.describe(channel="Channel to remove")
        async def channel_remove(interaction: discord.Interaction, channel: discord.TextChannel):
            if interaction.guild is None:
                await interaction.response.send_message(embed=utils.error_embed("Server Only", "Channel settings only work in servers!"), ephemeral=True)
                return
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(embed=utils.no_permission_embed(), ephemeral=True)
                return
            settings = database.get_server_settings(interaction.guild.id)
            whitelist = settings['channel_whitelist']
            if channel.id not in whitelist:
                await interaction.response.send_message(embed=utils.error_embed("Not Found", "That channel isn't in the list!"), ephemeral=True)
                return
            whitelist = [cid for cid in whitelist if cid != channel.id]
            if database.set_channel_whitelist(interaction.guild.id, whitelist):
                suffix = " Responding in all channels now." if not whitelist else ""
                await interaction.response.send_message(embed=utils.success_embed("Channel Removed", f"Removed {channel.mention}.{suffix}"))
            else:
                await interaction.response.send_message(embed=utils.error_embed("Error", "Failed to update channel list!"), ephemeral=True)

        @channel_group.command(name="clear", description="Remove all channel restrictions — respond everywhere (admin only)")
        async def channel_clear(interaction: discord.Interaction):
            if interaction.guild is None:
                await interaction.response.send_message(embed=utils.error_embed("Server Only", "Channel settings only work in servers!"), ephemeral=True)
                return
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(embed=utils.no_permission_embed(), ephemeral=True)
                return
            if database.set_channel_whitelist(interaction.guild.id, []):
                await interaction.response.send_message(embed=utils.success_embed("Restrictions Cleared", "Responding in all channels."))
            else:
                await interaction.response.send_message(embed=utils.error_embed("Error", "Failed to clear channel restrictions!"), ephemeral=True)

        self.tree.add_command(channel_group)

        # ── /preset ───────────────────────────────────────────────────────────
        preset_group = app_commands.Group(name="preset", description="Save and load personality presets")

        @preset_group.command(name="list", description="List all saved presets")
        async def preset_list(interaction: discord.Interaction):
            if interaction.guild is None:
                await interaction.response.send_message(embed=utils.error_embed("Server Only", "Presets only work in servers!"), ephemeral=True)
                return
            presets = database.get_presets(interaction.guild.id)
            if not presets:
                await interaction.response.send_message(embed=utils.create_embed("Presets", "No presets saved yet! Use `/preset save <name>` to save the current personality."))
                return
            text = '\n'.join(f'• `{p["name"]}`' for p in presets)
            await interaction.response.send_message(embed=utils.create_embed("Saved Presets", text))

        @preset_group.command(name="save", description="Save the current personality as a named preset (admin only)")
        @app_commands.describe(name="Name for this preset")
        async def preset_save(interaction: discord.Interaction, name: str):
            if interaction.guild is None:
                await interaction.response.send_message(embed=utils.error_embed("Server Only", "Presets only work in servers!"), ephemeral=True)
                return
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(embed=utils.no_permission_embed(), ephemeral=True)
                return
            current_prompt = database.get_server_prompt(interaction.guild.id)
            if database.save_preset(interaction.guild.id, name, current_prompt):
                await interaction.response.send_message(embed=utils.success_embed("Preset Saved", f"Saved current personality as `{name}`."))
            else:
                await interaction.response.send_message(embed=utils.error_embed("Error", "Failed to save preset!"), ephemeral=True)

        @preset_group.command(name="load", description="Load a saved preset as the active personality (admin only)")
        @app_commands.describe(name="Name of the preset to load")
        async def preset_load(interaction: discord.Interaction, name: str):
            if interaction.guild is None:
                await interaction.response.send_message(embed=utils.error_embed("Server Only", "Presets only work in servers!"), ephemeral=True)
                return
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(embed=utils.no_permission_embed(), ephemeral=True)
                return
            prompt = database.load_preset(interaction.guild.id, name)
            if prompt is None:
                await interaction.response.send_message(embed=utils.error_embed("Not Found", f"No preset named `{name}`!"), ephemeral=True)
                return
            if database.set_server_prompt(interaction.guild.id, prompt):
                database.add_prompt_history(interaction.guild.id, prompt, interaction.user.id)
                await interaction.response.send_message(embed=utils.success_embed("Preset Loaded", f"Loaded personality preset `{name}`."))
            else:
                await interaction.response.send_message(embed=utils.error_embed("Error", "Failed to load preset!"), ephemeral=True)

        @preset_group.command(name="delete", description="Delete a saved preset (admin only)")
        @app_commands.describe(name="Name of the preset to delete")
        async def preset_delete(interaction: discord.Interaction, name: str):
            if interaction.guild is None:
                await interaction.response.send_message(embed=utils.error_embed("Server Only", "Presets only work in servers!"), ephemeral=True)
                return
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(embed=utils.no_permission_embed(), ephemeral=True)
                return
            if database.delete_preset(interaction.guild.id, name):
                await interaction.response.send_message(embed=utils.success_embed("Preset Deleted", f"Deleted preset `{name}`."))
            else:
                await interaction.response.send_message(embed=utils.error_embed("Not Found", f"No preset named `{name}`!"), ephemeral=True)

        self.tree.add_command(preset_group)

        # ── /model ────────────────────────────────────────────────────────────
        model_group = app_commands.Group(name="model", description="Manage which AI model is used")

        async def model_autocomplete(interaction: discord.Interaction, current: str):
            return [
                app_commands.Choice(name=m, value=m)
                for m in config.MODEL_WHITELIST
                if current.lower() in m.lower()
            ][:25]

        @model_group.command(name="list", description="Show available models and the currently active one")
        async def model_list(interaction: discord.Interaction):
            current = database.get_server_model(interaction.guild.id) if interaction.guild else config.MODEL_NAME
            if not config.MODEL_WHITELIST:
                await interaction.response.send_message(embed=utils.create_embed(
                    "Active Model",
                    f"Using `{current}`\n\nModel switching is disabled — set `MODEL_WHITELIST` in your `.env` to enable it.",
                ))
                return
            text = '\n'.join(
                f'• `{m}` ← active' if m == current else f'• `{m}`'
                for m in config.MODEL_WHITELIST
            )
            await interaction.response.send_message(embed=utils.create_embed("Available Models", text))

        @model_group.command(name="set", description="Set the AI model for this server (admin only)")
        @app_commands.describe(model="Model name to use")
        @app_commands.autocomplete(model=model_autocomplete)
        async def model_set(interaction: discord.Interaction, model: str):
            if interaction.guild is None:
                await interaction.response.send_message(embed=utils.error_embed("Server Only", "Model settings only work in servers!"), ephemeral=True)
                return
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(embed=utils.no_permission_embed(), ephemeral=True)
                return
            if not config.MODEL_WHITELIST:
                await interaction.response.send_message(
                    embed=utils.error_embed("Model Switching Disabled", "Set `MODEL_WHITELIST` in your `.env` to enable model switching."),
                    ephemeral=True,
                )
                return
            if model not in config.MODEL_WHITELIST:
                await interaction.response.send_message(
                    embed=utils.error_embed("Invalid Model", f"`{model}` is not in the allowed list. Use `/model list` to see options."),
                    ephemeral=True,
                )
                return
            if database.set_server_model(interaction.guild.id, model):
                await interaction.response.send_message(embed=utils.success_embed("Model Updated", f"Now using `{model}`."))
            else:
                await interaction.response.send_message(embed=utils.error_embed("Error", "Failed to update model!"), ephemeral=True)

        @model_group.command(name="reset", description="Reset to the default model (admin only)")
        async def model_reset(interaction: discord.Interaction):
            if interaction.guild is None:
                await interaction.response.send_message(embed=utils.error_embed("Server Only", "Model settings only work in servers!"), ephemeral=True)
                return
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(embed=utils.no_permission_embed(), ephemeral=True)
                return
            if database.set_server_model(interaction.guild.id, ''):
                await interaction.response.send_message(embed=utils.success_embed("Model Reset", f"Reverted to default: `{config.MODEL_NAME}`."))
            else:
                await interaction.response.send_message(embed=utils.error_embed("Error", "Failed to reset model!"), ephemeral=True)

        self.tree.add_command(model_group)

        # ── /history ──────────────────────────────────────────────────────────
        history_group = app_commands.Group(name="history", description="View and restore past system prompts")

        @history_group.command(name="list", description="Show the last 10 system prompts (admin only)")
        async def history_list(interaction: discord.Interaction):
            if interaction.guild is None:
                await interaction.response.send_message(embed=utils.error_embed("Server Only", "Prompt history only works in servers!"), ephemeral=True)
                return
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(embed=utils.no_permission_embed(), ephemeral=True)
                return
            history = database.get_prompt_history(interaction.guild.id)
            if not history:
                await interaction.response.send_message(embed=utils.create_embed("Prompt History", "No history yet!"), ephemeral=True)
                return
            fields = [
                {'name': f"ID {h['id']} — {h['set_at']}", 'value': f"```{h['prompt'][:200]}```", 'inline': False}
                for h in history
            ]
            await interaction.response.send_message(
                embed=utils.create_embed("Prompt History", "Use `/history load <id>` to restore a past prompt.", fields),
                ephemeral=True,
            )

        @history_group.command(name="load", description="Restore a prompt from history by its ID (admin only)")
        @app_commands.describe(id="The history entry ID shown in /history list")
        async def history_load(interaction: discord.Interaction, id: int):
            if interaction.guild is None:
                await interaction.response.send_message(embed=utils.error_embed("Server Only", "Prompt history only works in servers!"), ephemeral=True)
                return
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(embed=utils.no_permission_embed(), ephemeral=True)
                return
            entry = database.get_prompt_history_entry(interaction.guild.id, id)
            if entry is None:
                await interaction.response.send_message(embed=utils.error_embed("Not Found", f"No history entry with ID `{id}`!"), ephemeral=True)
                return
            if database.set_server_prompt(interaction.guild.id, entry['prompt']):
                database.add_prompt_history(interaction.guild.id, entry['prompt'], interaction.user.id)
                await interaction.response.send_message(embed=utils.success_embed(
                    "Prompt Restored",
                    f"Restored prompt from `{entry['set_at']}`.",
                    [{'name': 'Prompt', 'value': f"```{entry['prompt'][:900]}```"}],
                ))
            else:
                await interaction.response.send_message(embed=utils.error_embed("Error", "Failed to restore prompt!"), ephemeral=True)

        self.tree.add_command(history_group)

        # ── Global error handler ──────────────────────────────────────────────
        @self.tree.error
        async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
            logger.error(f"Unhandled app command error: {error}", exc_info=True)
            embed = utils.error_embed("Error", "An unexpected error occurred!")
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)

        logger.info("Slash commands registered")
