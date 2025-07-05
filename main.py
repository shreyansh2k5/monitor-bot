import os
import discord
import asyncio
from dotenv import load_dotenv # Used for loading .env file during local development (though not for tokens in this setup)
from flask import Flask, request # Import Flask for the web server

# Initialize Flask app (this will run in a separate thread/task)
app = Flask(__name__)

@app.route('/')
def home():
    """
    A simple home route for the web server. Render uses this to check if the service is alive.
    """
    return "Discord Monitor Bot is running!"

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
class MonitorBot(discord.Client):
    """
    The main Discord bot that listens for commands and reports on the status
    of other configured bots.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.monitored_bots_config = [] # Stores configuration for bots to monitor (name, token)
        self.monitored_bot_clients = {} # Stores active MonitoredBotClient instances
        
        # Get the Discord channel ID where reports should be sent from environment variables.
        # It's crucial to convert it to an integer.
        self.target_channel_id = int(os.getenv("MONITOR_CHANNEL_ID")) 
        self.command_prefix = "!" # The prefix for commands this bot responds to

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
        print(f"Ready to monitor! Use '{self.command_prefix}monitor' in the designated channel.")

    async def on_message(self, message: discord.Message):
        """
        Event handler called whenever a message is sent in a channel the bot can see.
        """
        # Ignore messages sent by the bot itself to prevent infinite loops
        if message.author == self.user:
            return

        # Check if the message is in the target monitoring channel and is the correct command
        if message.channel.id == self.target_channel_id and message.content == f"{self.command_prefix}monitor":
            print(f"Received '{self.command_prefix}monitor' command from {message.author} in channel {message.channel.name}")
            await self.send_monitoring_report(message.channel)

    async def send_monitoring_report(self, channel: discord.TextChannel):
        """
        Generates and sends a detailed monitoring report to the specified channel.
        """
        report_message = "📊 **Discord Bot Monitoring Report** 📊\n\n"
        
        # Iterate through each monitored bot client to gather its stats
        for bot_name, client in self.monitored_bot_clients.items():
            report_message += f"--- **{bot_name}** ---\n"
            
            # Check if the monitored bot client has successfully logged in and is ready
            if client.is_ready and client.user: # client.user will be None if not logged in
                report_message += f"Status: Online ✅\n"
                report_message += f"Servers: {len(client.guilds)} 🌐\n"
                report_message += f"Latency: {client.latency * 1000:.2f} ms ⏱️\n" # Convert to milliseconds
                
                # Get and format the bot's activity
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
                
                # Get and format the bot's user status (online, idle, dnd, offline)
                report_message += f"User Status: {client.status.name.capitalize()}\n"
            else:
                report_message += "Status: Offline ❌ (Could not log in or not ready yet)\n"
            report_message += "\n" # Add a newline for separation between bots
        
        print("Sending monitoring report...")
        # Send the compiled report message to the channel
        await channel.send(report_message)

# Function to run the Flask app in a separate thread
def run_flask_app():
    """
    Runs the Flask web server. This function will be executed in a separate thread
    to avoid blocking the main Discord bot's asyncio event loop.
    """
    port = int(os.environ.get("PORT", 5000)) # Get port from Render's environment variable or default to 5000
    app.run(host="0.0.0.0", port=port)

# Main execution block
if __name__ == "__main__":
    # Load environment variables from .env file (for local development only)
    load_dotenv() 

    # Get the monitor bot's token from environment variables
    monitor_bot_token = os.getenv("MONITOR_BOT_TOKEN")
    if not monitor_bot_token:
        print("Error: MONITOR_BOT_TOKEN environment variable not set. Please set it on Render.")
        exit(1) # Exit if the main bot token is missing

    # Define intents for the monitor bot.
    intents = discord.Intents.default()
    intents.guilds = True
    intents.message_content = True
    intents.presences = True 

    # Create an instance of our MonitorBot
    monitor_client = MonitorBot(intents=intents)
    
    # Run the Flask app in a separate thread.
    # This allows the web server to run concurrently with the Discord bot.
    import threading
    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.daemon = True # Allow the main program to exit even if this thread is still running
    flask_thread.start()
    print(f"Flask web server started on port {os.environ.get('PORT', 5000)}")

    # Run the monitor bot. This is a blocking call that keeps the bot running.
    try:
        monitor_client.run(monitor_bot_token)
    except discord.LoginFailure:
        print("Error: Monitor bot token is invalid. Please check MONITOR_BOT_TOKEN environment variable on Render.")
    except Exception as e:
        print(f"An unexpected error occurred while running the monitor bot: {e}")

