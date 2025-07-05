// Load environment variables from a .env file (for local development)
// On platforms like Render, these are typically set directly in the environment.
require('dotenv').config();

// Import necessary classes from the discord.js library
const { Client, GatewayIntentBits, Partials, ActivityType } = require('discord.js');
const http = require('http'); // Import Node.js's built-in http module for the web server

// Retrieve bot token and monitor channel ID from environment variables
const MONITOR_BOT_TOKEN = process.env.MONITOR_BOT_TOKEN;
const MONITOR_CHANNEL_ID = process.env.MONITOR_CHANNEL_ID; // The ID of the channel where commands are expected
const PORT = process.env.PORT || 3000; // Get port from Render's environment variable or default to 3000

// Validate that essential environment variables are set
if (!MONITOR_BOT_TOKEN) {
    console.error("Error: MONITOR_BOT_TOKEN environment variable not set. Please set it.");
    process.exit(1);
}
if (!MONITOR_CHANNEL_ID) {
    console.error("Error: MONITOR_CHANNEL_ID environment variable not set. Please set it.");
    process.exit(1);
}

// Convert MONITOR_CHANNEL_ID to a BigInt for comparison with Discord's snowflake IDs
const targetChannelId = BigInt(MONITOR_CHANNEL_ID);

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
const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMembers,
        GatewayIntentBits.GuildPresences,
        GatewayIntentBits.MessageContent // Necessary for reading message content for prefix commands
    ],
    partials: [Partials.Channel, Partials.GuildMember, Partials.Message, Partials.User] // Recommended partials for some events
});

/**
 * Event handler for when the bot is ready and connected to Discord.
 */
client.once('ready', () => {
    console.log(`Monitor bot is ready! Logged in as ${client.user.tag}`);
    client.user.setActivity('your bots', { type: ActivityType.Watching }); // Set bot's activity status
});

/**
 * Event handler for when a message is created in a channel.
 * This is where prefix commands are processed.
 */
client.on('messageCreate', async message => {
    // Ignore messages from other bots or webhooks to prevent infinite loops or unwanted responses.
    if (message.author.bot || message.webhookId) {
        return;
    }

    // Check if the message was sent in the designated monitoring channel.
    // If not, ignore it to keep command usage organized.
    if (message.channel.id !== targetChannelId.toString()) { // Compare string IDs
        return;
    }

    const messageContent = message.content.trim(); // Get the trimmed content of the message
    const prefix = '!'; // Define the command prefix

    // Handle the "!monitor_all" command
    if (messageContent === `${prefix}monitor_all`) {
        await handleMonitorAllCommand(message);
    } 
    // Handle the "!monitor <bot_name>" command
    else if (messageContent.startsWith(`${prefix}monitor `)) {
        const args = messageContent.slice(prefix.length).trim().split(/ +/);
        const command = args.shift().toLowerCase(); // Should be 'monitor'
        const botName = args.join(' '); // Get the rest as bot name

        if (command === 'monitor' && botName) {
            await handleMonitorCommand(message, botName);
        } else {
            // If no bot name is provided, send a usage message.
            await message.channel.send(`Usage: \`${prefix}monitor <bot_name>\``);
        }
    }
});

/**
 * Generates a detailed monitoring report for a single bot.
 * @param {User} botUser The User object of the bot.
 * @param {Guild} guild The Guild object where the bot is found.
 * @returns {string} The formatted report string for the bot.
 */
function generateSingleBotReport(botUser, guild) {
    const member = guild.members.cache.get(botUser.id); // Get the Member object for the bot in this guild

    let report = `--- **${botUser.username}** ---\n`;
    report += `ID: ${botUser.id}\n`;
    report += `In Guild: ${guild.name} (ID: ${guild.id})\n`;

    if (member) {
        // Check presence status
        const presence = member.presence;
        if (presence) {
            report += `Status: ${presence.status.toUpperCase()} ${getEmojiForStatus(presence.status)}\n`;

            // Display activities
            if (presence.activities && presence.activities.length > 0) {
                report += `Activity:\n`;
                presence.activities.forEach(activity => {
                    let activityString = `- ${activity.type.toString().replace(/_/g, ' ').toLowerCase()}: ${activity.name}`;
                    if (activity.details) activityString += ` - ${activity.details}`;
                    if (activity.state) activityString += ` (${activity.state})`;
                    if (activity.url) activityString += ` (${activity.url})`;
                    report += `  ${activityString}\n`;
                });
            } else {
                report += `Activity: No activity set\n`;
            }
        } else {
            report += `Status: Offline ❌ (Presence data not available)\n`;
        }
    } else {
        report += `Status: Not found in this guild (or member data not cached) ❌\n`;
    }
    return report;
}

/**
 * Returns an emoji based on the Discord user status.
 * @param {string} status The status string (online, idle, dnd, offline).
 * @returns {string} An emoji representing the status.
 */
function getEmojiForStatus(status) {
    switch (status) {
        case 'online': return '✅';
        case 'idle': return '🌙';
        case 'dnd': return '⛔';
        case 'offline': return '❌';
        default: return '❓'; // Unknown status
    }
}

/**
 * Handles the "!monitor_all" command by generating a report for all bots
 * visible in shared guilds.
 * @param {Message} message The message object that triggered the command.
 */
async function handleMonitorAllCommand(message) {
    let report = "📊 **Discord Bot Monitoring Report** 📊\n\n";
    let foundAnyBot = false;

    // Iterate through all guilds (servers) that the monitor bot is a part of.
    for (const [guildId, guild] of client.guilds.cache) {
        // Ensure members are cached for presence and activity data
        // This might require the GUILD_MEMBERS intent and potentially fetching members if not all are cached.
        try {
            await guild.members.fetch(); // Fetch all members to ensure presence data is available
        } catch (error) {
            console.error(`Could not fetch members for guild ${guild.name} (ID: ${guild.id}):`, error);
            // Continue without full member list for this guild if fetch fails
        }

        const botsInGuild = guild.members.cache.filter(member => member.user.bot);

        if (botsInGuild.size > 0) {
            foundAnyBot = true;
            report += `--- **Bots in ${guild.name}** ---\n`;
            botsInGuild.forEach(botMember => {
                report += generateSingleBotReport(botMember.user, guild) + "\n";
            });
            report += "\n"; // Add a newline for separation between guilds' reports
        }
    }

    if (!foundAnyBot) {
        report += "No bots found in shared servers. Make sure your monitor bot is in servers with other bots.\n";
    }

    // Send the complete report to the channel, splitting if it's too long for a single message.
    await sendLongMessage(message.channel, report);
}

/**
 * Handles the "!monitor <bot_name>" command by generating a report for a specific bot.
 * @param {Message} message The message object that triggered the command.
 * @param {string} targetBotName The name of the bot to monitor.
 */
async function handleMonitorCommand(message, targetBotName) {
    let report = `Monitoring bot: **${targetBotName}**\n\n`;
    let botFound = false;

    for (const [guildId, guild] of client.guilds.cache) {
        try {
            await guild.members.fetch(); // Fetch all members to ensure presence data is available
        } catch (error) {
            console.error(`Could not fetch members for guild ${guild.name} (ID: ${guild.id}):`, error);
            continue; // Skip to next guild if fetch fails
        }

        const foundBotMember = guild.members.cache.find(
            member => member.user.bot && member.user.username.toLowerCase() === targetBotName.toLowerCase()
        );

        if (foundBotMember) {
            botFound = true;
            report += generateSingleBotReport(foundBotMember.user, guild) + "\n";
            break; // Found the bot, no need to check other guilds for this specific command
        }
    }

    if (!botFound) {
        report += `Bot '${targetBotName}' not found in any shared servers.`;
    }

    await message.channel.send(report);
}

/**
 * Sends a potentially long message by splitting it into chunks if it exceeds Discord's message limit.
 * @param {TextChannel | DMChannel} channel The channel to send the message to.
 * @param {string} content The full message content.
 */
async function sendLongMessage(channel, content) {
    const MAX_LENGTH = 2000; // Discord's message character limit

    if (content.length <= MAX_LENGTH) {
        await channel.send(content);
        return;
    }

    // Split the message into chunks
    let currentContent = content;
    while (currentContent.length > 0) {
        let chunk = currentContent.substring(0, MAX_LENGTH);
        currentContent = currentContent.substring(MAX_LENGTH);
        await channel.send(chunk);
        // Add a small delay between sending chunks to avoid rate limits
        await new Promise(resolve => setTimeout(resolve, 1000)); 
    }
}

// Create a simple HTTP server to listen on the specified port.
// This is required by platforms like Render to detect an open port and consider the service live.
const server = http.createServer((req, res) => {
    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end('Discord Monitor Bot is running!\n');
});

server.listen(PORT, () => {
    console.log(`HTTP server listening on port ${PORT}`);
});

// Log in to Discord with your bot's token
client.login(MONITOR_BOT_TOKEN)
    .catch(error => {
        console.error("Failed to log in to Discord:", error);
        process.exit(1);
    });
