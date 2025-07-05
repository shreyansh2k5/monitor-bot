import { Client, GatewayIntentBits } from 'discord.js';
import 'dotenv/config';
import http from 'http'; // Import the http module

// Initialize Discord Client with necessary intents
const client = new Client({
    intents: [
        GatewayIntentBits.Guilds, // Required to get guild (server) information
        GatewayIntentBits.GuildMessages, // Required to read messages for commands
        GatewayIntentBits.MessageContent // Required to access message content for commands
    ]
});

// Bot token from environment variables
const TOKEN = process.env.DISCORD_BOT_TOKEN;
const REPORT_CHANNEL_ID = process.env.REPORT_CHANNEL_ID; // Channel where information will be sent
const PORT = process.env.PORT || 3000; // Render sets the PORT environment variable

// Create a simple HTTP server to satisfy Render's web service requirement
const server = http.createServer((req, res) => {
    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end('Monitor Bot is alive!\n');
});

server.listen(PORT, () => {
    console.log(`HTTP server listening on port ${PORT}`);
});

client.once('ready', () => {
    console.log(`Monitor Bot is online! Logged in as ${client.user.tag}`);
});

client.on('messageCreate', async message => {
    // Ignore messages from other bots or non-command messages
    if (message.author.bot || !message.content.startsWith('!monitor')) return;

    const args = message.content.slice('!monitor'.length).trim().split(/ +/);
    const command = args.shift().toLowerCase();

    if (command === 'status') {
        if (!REPORT_CHANNEL_ID) {
            return message.reply('REPORT_CHANNEL_ID is not set in environment variables.');
        }

        const reportChannel = client.channels.cache.get(REPORT_CHANNEL_ID);
        if (!reportChannel) {
            return message.reply(`Could not find the report channel with ID: ${REPORT_CHANNEL_ID}`);
        }

        let response = 'Monitoring the following bots and their server activities:\n\n';

        // Iterate through all guilds (servers) the monitor bot is in
        for (const guild of client.guilds.cache.values()) {
            response += `**Server:** ${guild.name} (ID: ${guild.id})\n`;
            response += `**Members:** ${guild.memberCount}\n`;

            // Filter for bots (assuming a bot is a user with `bot` flag set to true)
            const bots = guild.members.cache.filter(member => member.user.bot);

            if (bots.size > 0) {
                response += '**Bots in this server:**\n';
                bots.forEach(bot => {
                    // Exclude the monitor bot itself from the list of "other" bots
                    if (bot.user.id !== client.user.id) {
                        response += `- ${bot.user.tag} (ID: ${bot.user.id})\n`;
                    }
                });
            } else {
                response += 'No other bots found in this server.\n';
            }
            response += '\n';
        }

        try {
            await reportChannel.send(response);
            message.reply('Bot activity report sent to the designated channel!');
        } catch (error) {
            console.error('Error sending report:', error);
            message.reply('There was an error sending the report.');
        }
    }
});

// Log in to Discord
client.login(TOKEN);
