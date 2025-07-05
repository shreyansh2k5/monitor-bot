import os
import discord
import asyncio
from discord.ext import commands
from discord import app_commands # Import app_commands specifically for slash commands

# Define a custom client for each bot we want to monitor.
# This allows us to log in each monitored bot separately and get its specific data.
class MonitoredBotClient(discord.Client):
    """
    A custom discord.Client subclass for each bot being monitored.
    It logs in with the provided token and tracks its readiness.
    """
    def __init__(self, bot_token: str, bot_name: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot_token = bot_token
        self.bot_name = bot_name
        self.is_ready = False # Flag to indicate if this specific bot client has logged in and is ready

    async def on_ready(self):
        """
        Event handler called when the monitored bot client successfully logs in.
        """
        print(f"Monitored bot '{self.bot_name}' logged in as {self.user} (ID: {self.user.id})")
        self.is_ready = True # Set the readiness flag to True

# The main monitor bot client that will manage and report on other bots.
class MonitorBot(commands.Bot): # Inherit from commands.Bot for easier command handling
    """
    The main Discord bot that listens for commands and reports on the status
    of other configured bots.
    """
    def __init__(self, *args, **kwargs):
        # We don't need a command_prefix for slash commands, but commands.Bot requires it.
        # It's good practice to set it to an unused prefix if only using slash commands.
        super().__init__(command_prefix="!", *args, **kwargs) 
        self.monitored_bots_config = [] # Stores configuration for bots to monitor (name, token)
        self.monitored_bot_clients = {} # Stores active MonitoredBotClient instances
        
        # Get the Discord channel ID where reports should be sent from environment variables.
        # It's crucial to convert it to an integer.
        self.target_channel_id = int(os.getenv("MONITOR_CHANNEL_ID")) 

        # Add the slash commands to the command tree. This prepares them for syncing with Discord.
        self.tree.add_command(self.monitor_bot_command)
        self.tree.add_command(self.monitor_all_bots_command)

    async def setup_hook(self):
        """
        This method is called automatically by discord.py when the client is setting up.
        It's a good place to load configurations and start background tasks.
        """
        print("Monitor bot setup_hook started.")
        # Load monitored bot tokens and names from environment variables.
        # It iterates through BOT_TOKEN_1, BOT_TOKEN_2, etc., until one is not found.
        i = 1
        while True:
            token_env_var = f"BOT_TOKEN_{i}"
            name_env_var = f"BOT_NAME_{i}"
            token = os.getenv(token_env_var)
            name = os.getenv(name_env_var)
            
            if token and name:
                # Add the bot's configuration to our list
                self.monitored_bots_config.append({"name": name, "token": token})
                i += 1
            else:
                # Stop if no more BOT_TOKEN_X variables are found
                break
        
        print(f"Found {len(self.monitored_bots_config)} bots to monitor.")

        # For each configured bot, create a MonitoredBotClient instance and start it.
        for bot_info in self.monitored_bots_config:
            # Intents are crucial for monitored bots too. They need `presences` and `guilds`
            # to gather status, activity, and server count information.
            # IMPORTANT: For these intents to work, you MUST enable "Presence Intent" and
            # "Server Members Intent" in the Discord Developer Portal for EACH bot
            # (your monitor bot AND all monitored bots).
            client = MonitoredBotClient(bot_info["token"], bot_info["name"], intents=discord.Intents.default())
            client.intents.presences = True 
            client.intents.guilds = True # This allows the monitored bot client to know its guilds.
            
            # Store the client instance by its name for easy lookup
            self.monitored_bot_clients[bot_info["name"]] = client
            
            # Run each monitored bot in a separate asyncio task.
            # This allows all bots to log in and operate concurrently without blocking the main monitor bot's loop.
            asyncio.create_task(client.start(bot_info["token"]))
            
            # Add a small delay to allow the bot to attempt login.
            # This helps prevent hitting rate limits too quickly if many bots are started at once.
            await asyncio.sleep(2) # Adjust this delay if you have many bots or experience issues

    async def on_ready(self):
        """
        Event handler called when the main monitor bot successfully logs in.
        This is where slash commands are synced.
        """
        print(f"Monitor bot logged in as {self.user} (ID: {self.user.id})")
        print(f"Ready to monitor! Use slash commands like /monitor or /monitor_all.")
        
        # Sync slash commands. This is a critical section for your issue.
        # For immediate testing, it's highly recommended to sync to a specific guild.
        # Global sync can take up to an hour to propagate.
        guild_id = os.getenv("TEST_GUILD_ID") # Get test guild ID from environment variable

        if guild_id:
            try:
                # Convert guild_id to int. If not a valid integer, it falls back to global sync.
                guild_obj = discord.Object(id=int(guild_id))
                # If you want global commands to also show up in your test guild immediately,
                # you can uncomment the next line. Otherwise, for guild-specific commands only, keep it commented.
                # self.tree.copy_global_commands(guild=guild_obj) 
                await self.tree.sync(guild=guild_obj) # Sync specifically to this guild for fast testing.
                print(f"Slash commands synced to guild ID: {guild_id}")
            except ValueError:
                print(f"Error: TEST_GUILD_ID '{guild_id}' is not a valid integer. Please check your environment variable.")
                await self.tree.sync() # Fallback to global sync if guild ID is invalid.
                print("Falling back to global slash command sync.")
            except Exception as e:
                # Catches other errors during guild sync, falls back to global.
                print(f"Failed to sync slash commands to guild {guild_id}: {e}")
                await self.tree.sync() # Fallback to global sync on other errors.
                print("Falling back to global slash command sync.")
        else:
            try:
                await self.tree.sync() # Global sync (can take significant time for propagation).
                print("No TEST_GUILD_ID found. Slash commands synced globally.")
            except Exception as e:
                print(f"Failed to sync global slash commands: {e}")

    # Slash command definitions:
    # Use @app_commands.command decorator to define a slash command.
    @app_commands.command(name="monitor", description="Get detailed status for a specific monitored bot.")
    @app_commands.describe(bot_name="The name of the bot to monitor (e.g., MyAwesomeBot)")
    async def monitor_bot_command(self, interaction: discord.Interaction, bot_name: str):
        """
        Slash command to get the status of a single specified bot.
        """
        # Acknowledge the command immediately to prevent "Application did not respond" errors.
        await interaction.response.defer(ephemeral=False) 

        # Check if the command is used in the designated monitoring channel.
        if interaction.channel_id != self.target_channel_id:
            await interaction.followup.send(f"Please use this command in the designated monitoring channel: <#{self.target_channel_id}>", ephemeral=True)
            return

        bot_name_lower = bot_name.lower()
        found_client = None
        # Find the requested bot client (case-insensitive)
        for name, client in self.monitored_bot_clients.items():
            if name.lower() == bot_name_lower:
                found_client = client
                break
        
        if found_client:
            report_message = await self._generate_single_bot_report(found_client)
            await interaction.followup.send(report_message) # Send the report.
        else:
            await interaction.followup.send(f"Bot '{bot_name}' not found or not configured for monitoring. Available bots: {', '.join(self.monitored_bot_clients.keys())}")

    @app_commands.command(name="monitor_all", description="Get status for all configured monitored bots.")
    async def monitor_all_bots_command(self, interaction: discord.Interaction):
        """
        Slash command to get the status of all configured bots.
        """
        # Acknowledge the command immediately.
        await interaction.response.defer(ephemeral=False) 

        # Check if the command is used in the designated monitoring channel.
        if interaction.channel_id != self.target_channel_id:
            await interaction.followup.send(f"Please use this command in the designated monitoring channel: <#{self.target_channel_id}>", ephemeral=True)
            return

        report_message = await self._generate_full_report()
        await interaction.followup.send(report_message) # Send the full report.

    async def _generate_single_bot_report(self, client: MonitoredBotClient) -> str:
        """
        Generates a detailed monitoring report for a single bot.
        """
        report_message = f"--- **{client.bot_name}** ---\n"
        
        if client.is_ready and client.user: # Check if the bot successfully logged in.
            report_message += f"Status: Online ✅\n"
            report_message += f"Servers: {len(client.guilds)} 🌐\n"
            report_message += f"Latency: {client.latency * 1000:.2f} ms ⏱️\n" # Latency in milliseconds.
            
            # Display current activity.
            activity_str = "No activity set"
            if client.activity:
                if client.activity.type == discord.ActivityType.playing:
                    activity_str = f"Playing: {client.activity.name}"
                elif client.activity.type == discord.ActivityType.streaming:
                    activity_str = f"Streaming: {client.activity.name} ({client.activity.url})"
                elif client.activity.type == discord.ActivityType.listening:
                    activity_str = f"Listening to: {client.activity.name}"
                elif client.activity.type == discord.ActivityType.watching:
                    activity_str = f"Watching: {client.activity.name}"
                elif client.activity.type == discord.ActivityType.custom:
                    activity_str = f"Custom Status: {client.activity.name}"
                elif client.activity.type == discord.ActivityType.competing:
                    activity_str = f"Competing in: {client.activity.name}"
            report_message += f"Activity: {activity_str}\n"
            
            report_message += f"User Status: {client.status.name.capitalize()}\n" # Online, idle, dnd, offline.

            # Add server names to the report.
            if client.guilds:
                server_names = [guild.name for guild in client.guilds]
                report_message += f"Servers List: {', '.join(server_names)}\n"
            else:
                report_message += "Servers List: Not in any servers.\n"

        else:
            report_message += "Status: Offline ❌ (Could not log in or not ready yet)\n"
        
        return report_message

    async def _generate_full_report(self) -> str:
        """
        Generates a detailed monitoring report for all bots.
        """
        report_message = "📊 **Discord Bot Monitoring Report** 📊\n\n"
        
        # Iterate through all configured monitored bots and generate individual reports.
        for bot_name, client in self.monitored_bot_clients.items():
            report_message += await self._generate_single_bot_report(client)
            report_message += "\n" # Add a newline for separation between bots
        
        return report_message
