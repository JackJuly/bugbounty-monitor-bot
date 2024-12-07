import discord
import requests
from datetime import datetime
from discord.ext import commands, tasks

# Constants
DISCORD_TOKEN = 'YOUR_DISCORD_TOKEN'
CHANNEL_ID = 'YOUR_CHANNEL_ID'
ALLOWED_SERVERS = ['YOUR_SERVER_ID']
CHAOS_DATA_URL = "https://chaos-data.projectdiscovery.io/index.json"

# Veribles
monitor_list = []
chaos_data = {}
platform_name = {
    '': 'Self-hosted',
    'hackerone': 'HackerOne',
    'intigriti': 'Intigriti',
    'bugcrowd': 'Bugcrowd',
    'bugbountych': 'BugBounty Switzerland',
    'hackenproof': 'HackenProof',
    'yeswehack': 'YesWeHack'
}

# Discord Intents
intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
intents.message_content = True


# Functions

def fetch_chaos(url):
    try:
        r = requests.get(url=url)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
    except ValueError as e:
        print(f"Error decoding JSON: {e}")


def query_target(target):
    global chaos_data
    target_found = False
    for item in chaos_data:

        if 'name' in item and item['name'].lower() == target.lower():
            target_found = True
            return item

    if not target_found:
        return None


# Create Bot
bot = commands.Bot(command_prefix='/', intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    print(f"Bot is ready, ID: {bot.user.id}")
    for guild in bot.guilds:
        if str(guild.id) not in ALLOWED_SERVERS:
            await guild.leave()
            print(
                f"Left {guild.name} as it is not in the allowed servers list.")
    await bot.tree.sync()
    print(f"Slash commands synced successfully.")

    update_data.start()
    print("Scheduled update task started.")


# Scheduled update every 24 hours
@tasks.loop(hours=24)
async def update_data():
    global chaos_data

    result = fetch_chaos(CHAOS_DATA_URL)
    if result:
        chaos_data = result
        company_count = len(result)
        message = f"Chaos Data Updated ! Total companies: {company_count}\n"

        target_changes = []
        filtered_results = [
            item for item in chaos_data if item['name'] in monitor_list]

        for item in filtered_results:
            if item['change'] != 0:
                last_updated = datetime.strptime(
                    item['last_updated'][:26], "%Y-%m-%dT%H:%M:%S.%f")
                formatted_time = last_updated.strftime("%Y-%m-%d %H:%M")

                if item['change'] > 0:
                    change_symbol = f"▲ {item['change']}"
                else:
                    change_symbol = f"▼ {item['change']}"

                target_changes.append(
                    f"- **Target: {item['name']}**\n"
                    f"  - Subdomains: {item['count']}\n"
                    f"  - Change: {change_symbol}\n"
                    f"  - Last updated: {formatted_time}"
                )

        if target_changes:
            message += "\n### Target Changed❗️\n"
            message += "\n\n".join(target_changes)

        message_channel = bot.get_channel(int(CHANNEL_ID))
        if message_channel:
            await message_channel.send(message)
            print("Scheduled update")
        else:
            print("Channel not found.")
    else:
        print("Failed to fetch data or received no data.")


# Slash Commands
# /help: Show available commands and their descriptions
@bot.tree.command(name="help", description="Show the available commands and their descriptions.")
async def help(interaction: discord.Interaction):
    message = """
**Bug Bounty Monitor Bot Help**
Below are the available commands:
- `/help` : Show this help message.
  - Displays a list of available commands and their descriptions.
- `/query <target>` : Query information about a specific target.
  - Provides details of the target, including subdomains, platform, and last updated time.
- `/list` : Show the current monitoring targets.
  - Displays the list of all targets currently being monitored.
- `/add <target>` : Add a target to the monitoring list.
  - Adds a target to the monitoring list based on the target name.
- `/del <target>` : Remove a target from the monitoring list.
  - Removes a target from the monitoring list by the target name.
"""
    await interaction.response.send_message(message)


# /query <target>:  query a target
@bot.tree.command(name="query", description="Query information about a specific target.")
async def add(interaction: discord.Interaction, target: str):
    res = query_target(target)

    if res is not None:
        last_updated = datetime.strptime(
            res['last_updated'][:26], "%Y-%m-%dT%H:%M:%S.%f")
        formatted_time = last_updated.strftime("%Y-%m-%d %H:%M")

        message = f"""
### Target: {res['name']}
- **Subdomains**: {res['count']}
- **Platform**: [{platform_name[res['platform']]}]({res['program_url']})
- **Offers Reward**: {res['bounty']}
- **Last Updated**: {formatted_time}
"""
        message += f"[Download all the subdomains of {res['name']}]({res['URL']})"
        await interaction.response.send_message(message)
    else:
        await interaction.response.send_message(f"**_{target}_** not found in chaos data.")


# /list: show monitoring targets
@bot.tree.command(name="list", description="Show monitoring targets.")
async def list(interaction: discord.Interaction):
    if monitor_list:
        message = "**Monitoring List:**\n"
        for target in monitor_list:
            message += f"- {target}\n"
        await interaction.response.send_message(message)
    else:
        await interaction.response.send_message("\r\nMonitoring list is empty, use `/add` command to add targets.")


# /add <target>:  add a target
@bot.tree.command(name="add", description="Add a target to monitoring list.")
async def add(interaction: discord.Interaction, target: str):

    res = query_target(target)
    if res is not None:
        monitor_list.append(res['name'])
        await interaction.response.send_message(f"Added **_{target}_** to monitoring list.")
    else:
        await interaction.response.send_message(f"**_{target}_** not found in chaos data.")


# /del <target>: Remove a target
@bot.tree.command(name="del", description="Remove a target from monitoring list.")
async def del_item(interaction: discord.Interaction, target: str):
    if target in monitor_list:
        monitor_list.remove(target)
        await interaction.response.send_message(f"Removed **_{target}_** from monitoring list.")
    else:
        await interaction.response.send_message(f"**_{target}_** not found.")


# run bot
bot.run(DISCORD_TOKEN)
