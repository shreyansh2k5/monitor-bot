// deploy-commands.js - Slash Command Registration

require('dotenv').config(); // Load .env for local CLIENT_ID, GUILD_ID, TOKEN

const { REST, Routes } = require('discord.js');

// Get environment variables
const CLIENT_ID = process.env.CLIENT_ID;
const GUILD_ID = process.env.GUILD_ID; // Optional: For faster guild-specific command syncing
const MONITOR_BOT_TOKEN = process.env.MONITOR_BOT_TOKEN;

if (!CLIENT_ID || !MONITOR_BOT_TOKEN) {
    console.error("Error: CLIENT_ID and MONITOR_BOT_TOKEN must be set in .env for command deployment.");
    process.exit(1);
}

const commands = [
    {
        name: 'monitor',
        description: 'Get detailed status for a specific monitored bot.',
        options: [
            {
                name: 'bot_name',
                type: 3, // String type
                description: 'The name of the bot to monitor (e.g., MyAwesomeBot)',
                required: true,
            },
        ],
    },
    {
        name: 'monitor_all',
        description: 'Get status for all configured monitored bots.',
    },
    {
        name: 'leave_server',
        description: 'Make a monitored bot leave a specific server.',
        options: [
            {
                name: 'bot_name',
                type: 3, // String type
                description: 'The name of the bot to make leave the server (e.g., MyAwesomeBot)',
                required: true,
            },
            {
                name: 'server_id',
                type: 3, // String type (Discord IDs are strings)
                description: 'The ID of the server the bot should leave',
                required: true,
            },
        ],
    },
];

// Create a REST instance with your bot's token
const rest = new REST({ version: '10' }).setToken(MONITOR_BOT_TOKEN);

(async () => {
    try {
        console.log('Started refreshing application (/) commands.');

        if (GUILD_ID) {
            // Register commands for a specific guild (faster for testing)
            await rest.put(
                Routes.applicationGuildCommands(CLIENT_ID, GUILD_ID),
                { body: commands },
            );
            console.log(`Successfully reloaded application (/) commands for guild ID: ${GUILD_ID}`);
        } else {
            // Register commands globally (can take up to an hour to propagate)
            await rest.put(
                Routes.applicationCommands(CLIENT_ID),
                { body: commands },
            );
            console.log('Successfully reloaded application (/) commands globally.');
        }
    } catch (error) {
        console.error('Error refreshing commands:', error);
    }
})();
