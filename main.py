import os
import asyncio
import threading
from dotenv import load_dotenv # Used to load environment variables from a .env file locally.
from flask import Flask, request # Flask for the web server, 'request' is imported but not used in this file.
import discord # Import discord library for intents.

# Import the MonitorBot class from our new bot_monitor.py file
from bot_monitor import MonitorBot

# Initialize Flask app
app = Flask(__name__)

@app.route('/')
def home():
    """
    A simple home route for the web server. Render (your hosting service) uses this to check if the service is alive.
    """
    return "Discord Monitor Bot is running!"

# Function to run the Flask app in a separate thread
def run_flask_app():
    """
    Runs the Flask web server. This function will be executed in a separate thread
    to avoid blocking the main Discord bot's asyncio event loop. This is crucial
    for concurrent operation of the web server and the asynchronous Discord bot.
    """
    # Get port from Render's environment variable (PORT) or default to 5000.
    port = int(os.environ.get("PORT", 5000)) 
    app.run(host="0.0.0.0", port=port) # Flask server listens on all available interfaces.

# Main execution block
if __name__ == "__main__":
    # Load environment variables from .env file (for local development only).
    # On Render, environment variables are loaded directly by the platform.
    load_dotenv() 

    # Get the monitor bot's token from environment variables
    monitor_bot_token = os.getenv("MONITOR_BOT_TOKEN")
    if not monitor_bot_token:
        # Crucial check: if the main bot token is missing, the bot cannot log in.
        print("Error: MONITOR_BOT_TOKEN environment variable not set. Please set it on Render.")
        exit(1) # Exit if the main bot token is missing

    # Define intents for the monitor bot. Intents tell Discord which events your bot wants to receive.
    # - `discord.Intents.default()` provides common intents like guilds, members, messages.
    # - `intents.message_content = True` is necessary to read message content (like commands).
    # - `intents.presences = True` is crucial for getting activity and status of other bots.
    #   NOTE: For these intents (especially `presences`), you MUST enable "Presence Intent"
    #   and "Server Members Intent" in the Discord Developer Portal under your bot's settings
    #   (go to https://discord.com/developers/applications/, select your bot, go to "Bot" section,
    #   and toggle these intents ON).
    intents = discord.Intents.default()
    intents.guilds = True # Required for guild-related events, like seeing what servers a bot is in.
    intents.message_content = True # Required to process message content, though not directly used for slash commands here.
    intents.presences = True # Essential for monitoring online/offline status and activities of other bots.

    # Create an instance of our MonitorBot
    monitor_client = MonitorBot(intents=intents)
    
    # Run the Flask app in a separate thread.
    # This allows the web server to run concurrently with the Discord bot's asyncio event loop,
    # preventing one from blocking the other.
    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.daemon = True # Allow the main program to exit even if this thread is still running.
    flask_thread.start()
    print(f"Flask web server started on port {os.environ.get('PORT', 5000)}")

    # Run the monitor bot. This is a blocking call that keeps the bot running.
    try:
        monitor_client.run(monitor_bot_token)
    except discord.LoginFailure:
        print("Error: Monitor bot token is invalid. Please check MONITOR_BOT_TOKEN environment variable on Render.")
    except Exception as e:
        print(f"An unexpected error occurred while running the monitor bot: {e}")
