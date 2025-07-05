import os
import asyncio
import threading
from dotenv import load_dotenv
from flask import Flask, request

# Import the MonitorBot class from our new bot_monitor.py file
from bot_monitor import MonitorBot

# Initialize Flask app
app = Flask(__name__)

@app.route('/')
def home():
    """
    A simple home route for the web server. Render uses this to check if the service is alive.
    """
    return "Discord Monitor Bot is running!"

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
    # Intents tell Discord which events your bot wants to receive.
    # - `discord.Intents.default()` provides common intents like guilds, members, messages.
    # - `intents.message_content = True` is necessary to read message content (like commands).
    # - `intents.presences = True` is crucial for getting activity and status of other bots.
    #   Note: For bots in over 100 guilds, you might need to enable the "Presence Intent"
    #   and "Server Members Intent" in the Discord Developer Portal under your bot's settings.
    intents = discord.Intents.default()
    intents.guilds = True
    intents.message_content = True
    intents.presences = True 

    # Create an instance of our MonitorBot
    monitor_client = MonitorBot(intents=intents)
    
    # Run the Flask app in a separate thread.
    # This allows the web server to run concurrently with the Discord bot.
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

