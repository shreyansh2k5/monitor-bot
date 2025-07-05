// Load environment variables from a .env file (for local development)
// On platforms like Render, these are typically set directly in the environment.
require('dotenv').config(); // Correctly loads .env for local testing.

// Import necessary classes from the discord.js library
const { Client, GatewayIntentBits, Partials, ActivityType } = require('discord.js'); // Correct imports for JDA v14.
const http = require('http'); // Import Node.js's built-in http module for the web server. This is correct for Render's port binding.

// Retrieve bot token and monitor channel ID from environment variables
const MONITOR_BOT_TOKEN = process.env.MONITOR_BOT_TOKEN; // Correctly retrieves bot token.
const MONITOR_CHANNEL_ID = process.env.MONITOR_CHANNEL_ID; // Correctly retrieves channel ID.
const PORT = process.env.PORT || 3000; // Correctly retrieves port for the web server.

// Validate that essential environment variables are set
if (!MONITOR_BOT_TOKEN) { // Good error handling for missing token.
    console.error("Error: MONITOR_BOT_TOKEN environment variable not set. Please set it.");
    process.exit(1);
}
if (!MONITOR_CHANNEL_ID) { // Good error handling for missing channel ID.
    console.error("Error: MONITOR_CHANNEL_ID environment variable not set. Please set it.");
    process.exit(1);
}

// Convert MONITOR_CHANNEL_ID to a BigInt for comparison with Discord's snowflake IDs
const targetChannelId = BigInt(MONITOR_CHANNEL_ID); // Correctly converts channel ID to BigInt for robust comparison.

// Create a new Discord client instance with specified intents.
// Intents tell Discord which events your bot wants to receive.
// - GatewayIntentBits.Guilds: Required for guild-related events.
// - GatewayIntentBits.GuildMembers: Required to access member lists (including bots) in guilds.
// - GatewayIntentBits.GuildPresences: Required to get presence updates (online status, activity) of members.
// - GatewayIntentBits.MessageContent: CRUCIAL for reading message content for prefix commands.
// IMPORTANT: You MUST enable "Presence Intent" and "Server Members Intent"
// AND "Message Content Intent" in the Discord Developer Portal for your MONITOR BOT.
// Go to https://discord.com/developers/applications/, select your bot,
// go to "Bot" section, and toggle these intents ON.
const client = new Client({ // Client initialization with necessary intents. This part is correct.
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMembers,
        GatewayIntentBits.GuildPresences,
        GatewayIntentBits.MessageContent // Necessary for reading message content for prefix commands
    ],
    partials: [Partials.Channel, Partials.GuildMember, Partials.Message, Partials.User] // Recommended partials for some events. Correct.
});

/**
 * Event handler for when the bot is ready and connected to Discord.
 */
client.once('ready', () => { // Correct event listener for bot readiness.
    console.log(`Monitor bot is ready! Logged in as ${client.user.tag}`); // Logs successful login.
    client.user.setActivity('your bots', { type: ActivityType.Watching }); // Sets bot's activity. Correct.
});

/**
 * Event handler for when a message is created in a channel.
 * This is where prefix commands are processed.
 */
client.on('messageCreate', async message => { // Correct event listener for new messages.
    // --- DEBUGGING STEP: Log every message received ---
    console.log(`[DEBUG] Received message from ${message.author.tag} in #${message.channel.name}: ${message.content}`); // **CRUCIAL DEBUG LOG**

    // Ignore messages from other bots or webhooks to prevent infinite loops or unwanted responses.
    if (message.author.bot || message.webhookId) { // Correctly ignores other bots and webhooks.
        return;
    }

    // Check if the message was sent in the designated monitoring channel.
    // If not, ignore it to keep command usage organized.
    if (message.channel.id !== targetChannelId.toString()) { // Correctly checks if message is in target channel.
        console.log(`[DEBUG] Message not in target channel. Expected: ${targetChannelId}, Got: ${message.channel.id}`); // **CRUCIAL DEBUG LOG**
        return;
    }

    const messageContent = message.content.trim(); // Correctly trims message content.
    const prefix = '!'; // Correctly defines prefix.

    // Handle the "!monitor_all" command
    if (messageContent === `${prefix}monitor_all`) { // Correct command check.
        console.log(`[DEBUG] Executing !monitor_all command.`); // **CRUCIAL DEBUG LOG**
        await handleMonitorAllCommand(message); // Correct function call.
    } 
    // Handle the "!monitor <bot_name>" command
    else if (messageContent.startsWith(`${prefix}monitor `)) { // Correct command check.
        const args = messageContent.slice(prefix.length).trim().split(/ +/); // Correctly parses arguments.
        const command = args.shift().toLowerCase(); // Correctly gets command name.
        const botName = args.join(' '); // Correctly gets bot name.

        if (command === 'monitor' && botName) { // Correct argument validation.
            console.log(`[DEBUG] Executing !monitor command for bot: ${botName}`); // **CRUCIAL DEBUG LOG**
            await handleMonitorCommand(message, botName); // Correct function call.
        } else {
            // If no bot name is provided, send a usage message.
            console.log(`[DEBUG] Invalid !monitor command usage.`); // **CRUCIAL DEBUG LOG**
            await message.channel.send(`Usage: \`${prefix}monitor <bot_name>\``); // Correct usage message.
        }
    } else {
        console.log(`[DEBUG] Message is not a recognized command.`); // **CRUCIAL DEBUG LOG**
    }
});

// ... (generateSingleBotReport, getEmojiForStatus, handleMonitorAllCommand, handleMonitorCommand, sendLongMessage functions - these are all logically sound)

// Create a simple HTTP server to listen on the specified port.
// This is required by platforms like Render to detect an open port and consider the service live.
const server = http.createServer((req, res) => { // Correctly sets up a minimal HTTP server.
    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end('Discord Monitor Bot is running!\n');
});

server.listen(PORT, () => { // Correctly listens on the specified port.
    console.log(`HTTP server listening on port ${PORT}`);
});

// Log in to Discord with your bot's token
client.login(MONITOR_BOT_TOKEN) // Correctly logs in the Discord client.
    .catch(error => { // Good error handling for login failures.
        console.error("Failed to log in to Discord:", error);
        process.exit(1);
    });
