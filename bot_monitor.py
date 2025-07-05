import os
import discord
import asyncio
from discord.ext import commands

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
        # Set the command prefix to '!'
        super().__init__(command_prefix="!", *args, **kwargs) 
        self.monitored_bots_config = [] # Stores configuration for bots to monitor (name, token)
        self.monitored_bot_clients = {} # Stores active MonitoredBotClient instances
        
        # Get the Discord channel ID where reports should be sent from environment variables.
        # It's crucial to convert it to an integer.
        self.target_channel_id = int(os.getenv("MONITOR_CHANNEL_ID")) 

    async def setup_hook(self):
        """
        This method is called automatically by discord.py when the client is setting up.
        It's a good place to load configurations and start background tasks.
        """
        print("Monitor bot setup_hook started.")
        # Load monitored bot tokens and names from environment variables.
        # We expect variables like BOT_TOKEN_1, BOT_NAME_1, BOT_TOKEN_2, BOT_NAME_2, etc.
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
            # Intents are crucial. For monitoring, we need default intents which include guilds,
            # and specifically `presences` to get activity and status.
            # IMPORTANT: For these intents to work, you MUST enable "Presence Intent" and
            # "Server Members Intent" in the Discord Developer Portal for EACH bot
            # (your monitor bot AND all monitored bots).
            # Go to https://discord.com/developers/applications/, select your bot,
            # go to "Bot" section, and toggle these intents ON.
            client = MonitoredBotClient(bot_info["token"], bot_info["name"], intents=discord.Intents.default())
            client.intents.presences = True 
            client.intents.guilds = True
            
            # Store the client instance by its name for easy lookup
            self.monitored_bot_clients[bot_info["name"]] = client
            
            # Run each monitored bot in a separate asyncio task.
            # This allows all bots to log in and operate concurrently without blocking the main monitor bot.
            asyncio.create_task(client.start(bot_info["token"]))
            
            # Add a small delay to allow the bot to attempt login.
            # This helps prevent hitting rate limits too quickly if many bots are started at once.
            await asyncio.sleep(2) # Adjust this delay if you have many bots or experience issues

    async def on_ready(self):
        """
        Event handler called when the main monitor bot successfully logs in.
        """
        print(f"Monitor bot logged in as {self.user} (ID: {self.user.id})")
        print(f"Ready to monitor! Use prefix commands like !monitor or !monitor_all.")
        
        # No slash command syncing needed for prefix commands

    async def on_message(self, message):
        # Ignore messages from the bot itself to prevent infinite loops
        if message.author == self.user:
            return

        # --- DEBUGGING STEP: Print message content to logs ---
        print(f"Received message from {message.author}: {message.content}")

        # Process commands. This is crucial for commands.Bot to recognize and run your commands.
        await self.process_commands(message)

    @commands.command(name="monitor", description="Get detailed status for a specific monitored bot.")
    async def monitor_bot_command(self, ctx: commands.Context, bot_name: str):
        """
        Prefix command to get the status of a single specified bot.
        Usage: !monitor <bot_name>
        """
        # Check if the command is used in the designated monitoring channel.
        if ctx.channel.id != self.target_channel_id:
            await ctx.send(f"Please use this command in the designated monitoring channel: <#{self.target_channel_id}>")
            return

        bot_name_lower = bot_name.lower()
        found_client = None
        for name, client in self.monitored_bot_clients.items():
            if name.lower() == bot_name_lower:
                found_client = client
                break
        
        if found_client:
            report_message = await self._generate_single_bot_report(found_client)
            await ctx.send(report_message)
        else:
            await ctx.send(f"Bot '{bot_name}' not found or not configured for monitoring. Available bots: {', '.join(self.monitored_bot_clients.keys())}")

    @commands.command(name="monitor_all", description="Get status for all configured monitored bots.")
    async def monitor_all_bots_command(self, ctx: commands.Context):
        """
        Prefix command to get the status of all configured bots.
        Usage: !monitor_all
        """
        # Check if the command is used in the designated monitoring channel.
        if ctx.channel.id != self.target_channel_id:
            await ctx.send(f"Please use this command in the designated monitoring channel: <#{self.target_channel_id}>")
            return

        report_message = await self._generate_full_report()
        await ctx.send(report_message)

    async def _generate_single_bot_report(self, client: MonitoredBotClient) -> str:
        """
        Generates a detailed monitoring report for a single bot.
        """
        report_message = f"--- **{client.bot_name}** ---\n"
        
        if client.is_ready and client.user:
            report_message += f"Status: Online ✅\n"
            report_message += f"Servers: {len(client.guilds)} 🌐\n"
            report_message += f"Latency: {client.latency * 1000:.2f} ms ⏱️\n"
            
            activity_str = "No activity set"
            if client.activity:
                if client.activity.type == discord.ActivityType.playing:
                    activity_str = f"Playing: {client.activity.name}"
                elif client.activity.type == discord.ActivityType.streaming:
                    activity_str = f"Streaming: {client.activity.name} ({client.activity.url})"
                elif client.activity.type == discord.ActivityType.listening:
                    activity_str = f"Listening to: {client.activity.name}"
                elif client.activity.type == discord.ActivityType.custom:
                    activity_str = f"Custom Status: {client.activity.name}"
                elif client.activity.type == discord.ActivityType.competing:
                    activity_str = f"Competing in: {client.activity.name}"
            report_message += f"Activity: {activity_str}\n"
            
            report_message += f"User Status: {client.status.name.capitalize()}\n"

            # Add server names
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
        
        for bot_name, client in self.monitored_bot_clients.items():
            report_message += await self._generate_single_bot_report(client)
            report_message += "\n" # Add a newline for separation between bots
        
        return report_message
