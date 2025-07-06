// index.js - Main Bot Logic and Web Server

// Load environment variables from .env file (for local development)
require('dotenv').config();

const { Client, GatewayIntentBits, Collection, ActivityType } = require('discord.js');
const express = require('express');

// --- Express Web Server Setup ---
const app = express();
const port = process.env.PORT || 3000; // Render provides the PORT environment variable

app.get('/', (req, res) => {
    res.send('Discord Monitor Bot is running!');
});

app.listen(port, () => {
    console.log(`Express web server listening on port ${port}`);
});
// --- End Express Web Server Setup ---


// --- Discord Bot Setup ---

// Define intents for the main monitor bot.
const monitorBotIntents = [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildPresences,
    GatewayIntentBits.MessageContent,
];

// Create the main Discord client for the monitor bot
const monitorClient = new Client({ intents: monitorBotIntents });

// Collection to store active monitored bot clients
monitorClient.monitoredBotClients = new Collection();

// Get the Discord channel ID where reports should be sent from environment variables.
const targetChannelId = process.env.MONITOR_CHANNEL_ID;
if (!targetChannelId) {
    console.error("Error: MONITOR_CHANNEL_ID environment variable not set. Please set it on Render.");
    process.exit(1);
}

// Event: Main monitor bot is ready
monitorClient.once('ready', async () => {
    console.log(`Monitor bot logged in as ${monitorClient.user.tag}`);
    console.log(`Ready to monitor! Use slash commands like /monitor, /monitor_all, or /leave_server.`);

    // Load monitored bot tokens and names from environment variables.
    let i = 1;
    while (true) {
        const token = process.env[`BOT_TOKEN_${i}`];
        const name = process.env[`BOT_NAME_${i}`];

        if (token && name) {
            const monitoredBotIntents = [
                GatewayIntentBits.Guilds,
                GatewayIntentBits.GuildPresences,
                GatewayIntentBits.MessageContent,
            ];
            
            const monitoredBot = new Client({ intents: monitoredBotIntents });
            monitoredBot.botName = name; // Attach the name for easy access

            monitoredBot.once('ready', () => {
                console.log(`Monitored bot '${monitoredBot.botName}' logged in as ${monitoredBot.user.tag}`);
            });

            monitoredBot.on('error', (error) => {
                console.error(`Monitored bot '${monitoredBot.botName}' encountered an error:`, error);
            });

            try {
                await monitoredBot.login(token);
                monitorClient.monitoredBotClients.set(name.toLowerCase(), monitoredBot); // Store by lowercase name for lookup
                console.log(`Successfully logged in and added monitored bot: ${name}`);
            } catch (error) {
                console.error(`Failed to log in monitored bot '${name}': ${error.message}`);
            }
            i++;
            await new Promise(resolve => setTimeout(resolve, 2000)); // Small delay to avoid rate limits
        } else {
            break;
        }
    }
    console.log(`Monitoring ${monitorClient.monitoredBotClients.size} bots.`);
});

// Event: Handle slash commands
monitorClient.on('interactionCreate', async interaction => {
    if (!interaction.isChatInputCommand()) return;

    // Ensure the command is used in the designated monitoring channel
    if (interaction.channelId !== targetChannelId) {
        await interaction.reply({
            content: `Please use this command in the designated monitoring channel: <#${targetChannelId}>`,
            ephemeral: true
        });
        return;
    }

    // Defer reply immediately for all commands in the correct channel
    await interaction.deferReply({ ephemeral: false }); 

    const { commandName } = interaction;

    if (commandName === 'monitor') {
        const botName = interaction.options.getString('bot_name');
        const monitoredBot = monitorClient.monitoredBotClients.get(botName.toLowerCase());

        if (monitoredBot) {
            const report = generateSingleBotReport(monitoredBot);
            await interaction.editReply(report);
        } else {
            const availableBots = monitorClient.monitoredBotClients.map(client => client.botName).join(', ');
            await interaction.editReply(`Bot '${botName}' not found or not configured for monitoring. Available bots: ${availableBots || 'None'}`);
        }
    } else if (commandName === 'monitor_all') {
        const report = generateFullReport(monitorClient.monitoredBotClients);
        await interaction.editReply(report);
    } else if (commandName === 'leave_server') {
        const botName = interaction.options.getString('bot_name');
        const serverId = interaction.options.getString('server_id');

        const monitoredBot = monitorClient.monitoredBotClients.get(botName.toLowerCase());

        if (!monitoredBot) {
            const availableBots = monitorClient.monitoredBotClients.map(client => client.botName).join(', ');
            await interaction.editReply(`Bot '${botName}' not found or not configured for monitoring. Available bots: ${availableBots || 'None'}`);
            return;
        }

        try {
            const guild = await monitoredBot.guilds.fetch(serverId);
            if (guild) {
                await guild.leave();
                await interaction.editReply(`Successfully made bot '${botName}' leave server '${guild.name}' (ID: ${serverId}).`);
                console.log(`Bot '${botName}' left server '${guild.name}' (ID: ${serverId}).`);
            } else {
                await interaction.editReply(`Bot '${botName}' is not in a server with ID '${serverId}'.`);
            }
        } catch (error) {
            console.error(`Error making bot '${botName}' leave server '${serverId}':`, error);
            await interaction.editReply(`Failed to make bot '${botName}' leave server '${serverId}'. Error: ${error.message}`);
        }
    }
});

/**
 * Generates a detailed monitoring report for a single bot.
 * @param {Client} client The Discord.js client instance of the monitored bot.
 * @returns {string} The formatted report message.
 */
function generateSingleBotReport(client) {
    let reportMessage = `--- **${client.botName}** ---\n`;

    if (client.isReady() && client.user) { // client.isReady() checks if the client is ready
        reportMessage += `Status: Online ✅\n`;
        reportMessage += `Servers: ${client.guilds.cache.size} 🌐\n`;
        reportMessage += `Latency: ${client.ws.ping} ms ⏱️\n`; // WebSocket ping is latency

        // Get and format the bot's activity
        const activity = client.user.presence?.activities[0];
        let activityStr = "No activity set";
        if (activity) {
            switch (activity.type) {
                case ActivityType.Playing:
                    activityStr = `Playing: ${activity.name}`;
                    break;
                case ActivityType.Streaming:
                    activityStr = `Streaming: ${activity.name} (${activity.url})`;
                    break;
                case ActivityType.Listening:
                    activityStr = `Listening to: ${activity.name}`;
                    break;
                case ActivityType.Watching:
                    activityStr = `Watching: ${activity.name}`;
                    break;
                case ActivityType.Custom:
                    activityStr = `Custom Status: ${activity.state || activity.name}`;
                    break;
                case ActivityType.Competing:
                    activityStr = `Competing in: ${activity.name}`;
                    break;
                default:
                    activityStr = `Activity: ${activity.name}`;
            }
        }
        reportMessage += `Activity: ${activityStr}\n`;

        // Get and format the bot's user status (online, idle, dnd, offline)
        const userStatus = client.user.presence?.status || 'offline';
        reportMessage += `User Status: ${userStatus.charAt(0).toUpperCase() + userStatus.slice(1)}\n`;

        // Add server names and IDs
        if (client.guilds.cache.size > 0) {
            const serverList = client.guilds.cache.map(guild => `${guild.name} (ID: ${guild.id})`).join('\n - ');
            reportMessage += `Servers List:\n - ${serverList}\n`;
        } else {
            reportMessage += "Servers List: Not in any servers.\n";
        }

    } else {
        reportMessage += "Status: Offline ❌ (Could not log in or not ready yet)\n";
    }
    return reportMessage;
}

/**
 * Generates a detailed monitoring report for all bots.
 * @param {Collection<string, Client>} monitoredBotClients A collection of monitored bot clients.
 * @returns {string} The formatted full report message.
 */
function generateFullReport(monitoredBotClients) {
    let reportMessage = "📊 **Discord Bot Monitoring Report** 📊\n\n";

    if (monitoredBotClients.size === 0) {
        reportMessage += "No bots configured for monitoring.\n";
        return reportMessage;
    }

    monitoredBotClients.forEach(client => {
        reportMessage += generateSingleBotReport(client);
        reportMessage += "\n"; // Add a newline for separation between bots
    });

    return reportMessage;
}

// Login the main monitor bot
const monitorBotToken = process.env.MONITOR_BOT_TOKEN;
if (!monitorBotToken) {
    console.error("Error: MONITOR_BOT_TOKEN environment variable not set. Please set it on Render.");
    process.exit(1);
}

monitorClient.login(monitorBotToken).catch(error => {
    console.error("Failed to log in monitor bot:", error.message);
    process.exit(1);
});
