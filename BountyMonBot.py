import discord
import requests
import os
import zipfile
import shutil
import json
from datetime import datetime
from discord.ext import commands, tasks

# Constants
# Discord
DISCORD_TOKEN = 'YOUR_DISCORD_TOKEN'
CHANNEL_ID = 'YOUR_CHANNEL_ID'
ALLOWED_SERVERS = ['YOUR_SERVER_ID']

# ProjectDiscovery
PDCP_API_KEY = "YOUR_PDCP_API_KEY"
CHAOS_DATA_URL = "https://chaos-data.projectdiscovery.io/index.json"
CHAOS_DNS_URL = "https://dns.projectdiscovery.io/dns/"

# Varibles
monitor_list = []
chaos_data = []

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

# save monitor list
def save_list():
    with open('monitor_list.json', 'w') as f:
        json.dump(monitor_list, f)


# load monitor list
def load_list():
    global monitor_list
    try:
        with open('monitor_list.json', 'r') as f:
            monitor_list = json.load(f)
            print("Monitor List Loaded!")
        for target in monitor_list:
            download_data(target['URL'], first_time=True)
            print("Loaded targets' data downloaded!")
    except FileNotFoundError:
        monitor_list = []


# fetch chaos url
def fetch_chaos(url, query=""):
    try:
        r = requests.get(url=url+query)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
    except ValueError as e:
        print(f"Error decoding JSON: {e}")


# query target in search list
def query_target(target, search_list):

    target_found = False
    for item in search_list:

        if 'name' in item and item['name'].lower() == target.lower():
            target_found = True
            return item

    if not target_found:
        return None


# update chaos data
async def update_chaos_data():
    result = fetch_chaos(url=CHAOS_DATA_URL)

    if result:
        global chaos_data
        global changed_targets
        changed_targets = []

        chaos_data = result
        count_change = sum(1 for item in chaos_data if item["change"] != 0)
        message = f"Chaos Data Updated - **{count_change}** programs have changes"

        changes_message = []

        for idx, target in enumerate(monitor_list):

            item = next(
                (item for item in chaos_data if item['name'] == target['name']), None)

            if item:
                if item['change'] != 0 and item['last_updated'] != target['last_updated']:
                    last_updated = datetime.strptime(
                        item['last_updated'][:26], "%Y-%m-%dT%H:%M:%S.%f")
                    formatted_time = last_updated.strftime(
                        "%Y-%m-%d %H:%M")

                    changes_message.append(
                        f"- **Target: {item['name']}**\n"
                        f"  - Subdomains: {item['count']}\n"
                        f"  - Change: {'▲ ' + str(item['change']) if item['change'] > 0 else '▼ ' + str(item['change'])}\n"
                        f"  - Last updated: {formatted_time}"
                    )
                    changed_targets.append(item)
                monitor_list[idx] = item

        if changes_message:
            message += "\n### Target Changed❗️\n"
            message += "\n\n".join(changes_message)
            print("Monitored target changed!")
        else:
            print("Monitored target not changed.")
        return message
    else:
        print("Failed to fetch chaos data.")
        return "Failed to fetch chaos data."


def download_zip(url, path):

    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"URL link is invalid: {url}")
        return

    with open(path, 'wb') as f:
        f.write(response.content)
    print(f"Downloaded {path}")


# download target data
def download_data(url, first_time):
    if not url:
        return

    if not os.path.exists('./targets'):
        os.makedirs('./targets')

    target_name = url.split('/')[-1].replace('.zip', '')

    target_dir = f"./targets/{target_name}"
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    zip_path = f"./targets/{target_name}.zip"
    first_folder = f"{target_dir}/{target_name}_first"
    old_folder = f"{target_dir}/{target_name}_old"
    new_folder = f"{target_dir}/{target_name}_new"

    if not os.listdir(target_dir):

        download_zip(url, zip_path)
        os.makedirs(first_folder)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(first_folder)
        print(f"Extracted {zip_path} to {first_folder}")

    else:

        if not first_time:

            if not os.path.exists(old_folder):
                download_zip(url, zip_path)
                shutil.copytree(first_folder, old_folder)
                print(f"Copied {first_folder} to {old_folder}")

                os.makedirs(new_folder)
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(new_folder)
                print(f"Extracted {zip_path} to {new_folder}")

            else:
                download_zip(url, zip_path)
                shutil.rmtree(old_folder)
                print(f"Deleted {old_folder}")

                os.rename(new_folder, old_folder)
                print(f"Renamed {new_folder} to {old_folder}")

                os.makedirs(new_folder)
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(new_folder)
                print(f"Extracted {zip_path} to {new_folder}")
        else:

            print("No update needed.")

    if os.path.exists(zip_path):
        os.remove(zip_path)
        print(f"Deleted {zip_path}")


# query changed subdomains
def query_changes(target_name, change_since):
    new_folder = f"./targets/{target_name}/{target_name}_new"
    if change_since:
        old_folder = f"./targets/{target_name}/{target_name}_first"
    else:
        old_folder = f"./targets/{target_name}/{target_name}_old"

    if not os.path.exists(new_folder) or not os.path.exists(old_folder):
        print(f"Folders for target {target_name} do not exist.")
        return

    print('Querying changes...')

    new_subdomains = set()
    old_subdomains = set()

    for filename in os.listdir(new_folder):
        if filename.endswith(".txt"):
            with open(os.path.join(new_folder, filename), "r") as file:
                new_subdomains.update(line.strip()
                                      for line in file.readlines())

    for filename in os.listdir(old_folder):
        if filename.endswith(".txt"):
            with open(os.path.join(old_folder, filename), "r") as file:
                old_subdomains.update(line.strip()
                                      for line in file.readlines())

    new_added = new_subdomains - old_subdomains
    old_removed = old_subdomains - new_subdomains

    new_files = set(os.listdir(new_folder))
    old_files = set(os.listdir(old_folder))

    new_files_added = new_files - old_files
    old_files_removed = old_files - new_files

    result = {
        "new_added": new_added,
        "old_removed": old_removed,
        "new_files_added": new_files_added,
        "old_files_removed": old_files_removed
    }

    return result


# Create bot
bot = commands.Bot(command_prefix='/', intents=intents)


@bot.event
async def on_ready():
    load_list()
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
    update_message = await update_chaos_data()

    if update_message:
        for item in changed_targets:
            download_data(item['URL'], first_time=False)
            print(f"{item['name']}'s data downloaded and updated!")
        message_channel = bot.get_channel(int(CHANNEL_ID))
        if message_channel:
            await message_channel.send(update_message)
            print("Update Data Successfully.")
        else:
            print("Channel not found.")
    else:
        print("Failed to Update Data.")


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
- `/update` : Manually update chaos data.
  - Fetches and updates the chaos data from the ProjectDiscovery API.
- `/stats` : Show chaos data stats.
  - Displays statistics about the chaos data, including total programs, new programs, and changes.
- `/new` : Show new programs.
  - Lists new programs from the chaos data.
- `/changes <target>` : Show changes in domains for a specific target.
  - Displays changes in domains and subdomains for the given target.
- `/changes_since <target>` : Show changes in domains for a specific target since added to monitor list.
  - Displays changes in domains and subdomains for the given target since added to monitor list.
"""

    await interaction.response.send_message(message, ephemeral=True)


# /update: manually update data
@bot.tree.command(name="update", description="Manually update chaos data.")
async def update(interaction: discord.Interaction):
    update_message = await update_chaos_data()

    if update_message:
        await interaction.response.send_message(update_message, ephemeral=True)
        for item in changed_targets:
            download_data(item['URL'], first_time=False)
            print(f"{item['name']}'s data downloaded and updated!")
    else:
        await interaction.response.send_message("Failed to update data.", ephemeral=True)


# /query <target>:  query a target
@bot.tree.command(name="query", description="Query information about a specific target.")
async def add(interaction: discord.Interaction, target: str):
    res = query_target(target, chaos_data)

    if res is not None:
        last_updated = datetime.strptime(
            res['last_updated'][:26], "%Y-%m-%dT%H:%M:%S.%f")
        formatted_time = last_updated.strftime("%Y-%m-%d %H:%M")

        message = f"""
### Target: {res['name']}
- **Subdomains**: {res['count']}
- **Platform**: [{platform_name[res['platform']]}]({res['program_url']})
- **Offers Reward**: {res['bounty']}
"""
        if res['change'] != 0:
            message += f"- **Changes**: {res['change']}\n"
        message += f"- **Last Updated**: {formatted_time}\n"
        message += f"[Download all the subdomains of {res['name']}]({res['URL']})\n"
        await interaction.response.send_message(message, ephemeral=True)
    else:
        await interaction.response.send_message(f"**_{target}_** not found in chaos data.", ephemeral=True)


# /stats: show database stats
@bot.tree.command(name="stats", description="Show chaos data stats.")
async def stats(interaction: discord.Interaction):

    if chaos_data:
        count_program = len(chaos_data)
        count_new = sum(1 for program in chaos_data if program["is_new"])
        count_change = sum(1 for item in chaos_data if item["change"] != 0)
        stats = fetch_chaos(url=CHAOS_DNS_URL, query="stats")
        if stats:
            message = f"""
### Chaos Data Stats
- **Total programs**: {count_program}
- **New programs**: {count_new}
- **Changed programs**: {count_change}
- **Total records**: {stats['total']}
- **Last 24 hours**: {stats['new_last_24hour']}
"""
            await interaction.response.send_message(message, ephemeral=True)
        else:
            await interaction.response.send_message("\r\nFailed to fetch chaos stats.", ephemeral=True)

    else:
        await interaction.response.send_message("\r\nChaos data not found, use `/update` command to fetch data manually.", ephemeral=True)


# /new: show new programs
@bot.tree.command(name="new", description="Show new programs.")
async def new(interaction: discord.Interaction):

    if chaos_data:
        new_programs = [
            item for item in chaos_data if item["is_new"] is True
        ]
        if new_programs:
            message = f"### Found {len(new_programs)} New Programs.\n"
            for item in new_programs:
                message += f"- **[{item['name']}]({item['program_url']})**\n"
            await interaction.response.send_message(message, ephemeral=True)
        else:
            await interaction.response.send_message("\r\nNo new programs.", ephemeral=True)
    else:
        await interaction.response.send_message("\r\nChaos data not found, use `/update` command to fetch data manually.", ephemeral=True)


# /changes: Show changes in subdomains and files
@bot.tree.command(name="changes", description="Show changes in domains for a target.")
async def changes(interaction: discord.Interaction, target: str):

    res = query_target(target, monitor_list)

    if res:
        target_name = res['URL'].split('/')[-1].replace('.zip', '')
        result = query_changes(target_name, change_since=False)
        if result:
            if result["new_added"] or result["old_removed"] or result["new_files_added"] or result["old_files_removed"]:
                message = f"### Changes for {res['name']}:\n"

                new_domains = [os.path.splitext(f)[0]
                               for f in result.get("new_files_added", [])]
                if new_domains:
                    message += f"**[+] New domains:**\n"
                    message += "```\n"
                    for domain in new_domains:
                        message += f"{domain}\n"
                    message += "```\n"

                if result["new_added"]:
                    message += f"**[+] New subdomains:**\n"
                    message += "```\n"
                    for subdomain in result["new_added"]:
                        message += f"{subdomain}\n"
                    message += "```\n"

                removed_domains = [os.path.splitext(
                    f)[0] for f in result.get("old_files_removed", [])]
                if removed_domains:
                    message += f"**[-] Removed domains:**\n"
                    message += "```\n"
                    for domain in removed_domains:
                        message += f"{domain}\n"
                    message += "```\n"

                if result["old_removed"]:
                    message += f"**[-] Removed subdomains:**\n"
                    message += "```\n"
                    for subdomain in result["old_removed"]:
                        message += f"{subdomain}\n"
                    message += "```\n"

                await interaction.response.send_message(message, ephemeral=False)
            else:
                await interaction.response.send_message(f"No changes found for **{res['name']}**.", ephemeral=True)
        else:
            await interaction.response.send_message(f"No results found for **{res['name']}**.", ephemeral=True)
    else:
        await interaction.response.send_message(f"**{target}** not found in the monitoring list.", ephemeral=True)


# /changes_since: Show changes in subdomains and files since added
@bot.tree.command(name="changes_since", description="Show changes in domains for a target since added.")
async def changes_since(interaction: discord.Interaction, target: str):

    res = query_target(target, monitor_list)

    if res:
        target_name = res['URL'].split('/')[-1].replace('.zip', '')
        result = query_changes(target_name, change_since=True)
        if result:
            if result["new_added"] or result["old_removed"]:
                message = f"### Changes for {res['name']} since added:\n"

                new_domains = [os.path.splitext(f)[0]
                               for f in result.get("new_files_added", [])]
                if new_domains:
                    message += f"**[+] New domains:**\n"
                    message += "```\n"
                    for domain in new_domains:
                        message += f"{domain}\n"
                    message += "```\n"

                if result["new_added"]:
                    message += f"**[+] New subdomains:**\n"
                    message += "```\n"
                    for subdomain in result["new_added"]:
                        message += f"{subdomain}\n"
                    message += "```\n"

                removed_domains = [os.path.splitext(
                    f)[0] for f in result.get("old_files_removed", [])]
                if removed_domains:
                    message += f"**[-] Removed domains:**\n"
                    message += "```\n"
                    for domain in removed_domains:
                        message += f"{domain}\n"
                    message += "```\n"

                if result["old_removed"]:
                    message += f"**[-] Removed subdomains:**\n"
                    message += "```\n"
                    for subdomain in result["old_removed"]:
                        message += f"{subdomain}\n"
                    message += "```\n"

                await interaction.response.send_message(message, ephemeral=False)
            else:
                await interaction.response.send_message(f"No changes found for **{res['name']}** since added.", ephemeral=True)
        else:
            await interaction.response.send_message(f"No changes found for **{res['name']}** since added.", ephemeral=True)
    else:
        await interaction.response.send_message(f"**{target}** not found in the monitoring list.", ephemeral=True)


# /list: show monitoring targets
@bot.tree.command(name="list", description="Show monitoring targets.")
async def list(interaction: discord.Interaction):
    if monitor_list:
        message = "**Monitoring List:**\n"
        for target in monitor_list:
            message += f"- {target['name']}\n"
        await interaction.response.send_message(message, ephemeral=True)
    else:
        await interaction.response.send_message("\r\nMonitoring list is empty, use `/add` command to add targets.", ephemeral=True)


# /add <target>:  add a target
@bot.tree.command(name="add", description="Add a target to monitoring list.")
async def add(interaction: discord.Interaction, target: str):

    mon_res = query_target(target, monitor_list)
    if mon_res:
        await interaction.response.send_message(f"**_{mon_res['name']}_** is already in the monitoring list.", ephemeral=True)
        return
    res = query_target(target, chaos_data)
    if res is not None:
        monitor_list.append(res)
        await interaction.response.send_message(f"Added **_{res['name']}_** to monitoring list.", ephemeral=True)
        download_data(url=res['URL'], first_time=True)
    else:
        await interaction.response.send_message(f"**_{target}_** not found in chaos data.", ephemeral=True)


# /del <target>: Remove a target
@bot.tree.command(name="del", description="Remove a target from monitoring list.")
async def del_item(interaction: discord.Interaction, target: str):
    res = query_target(target, monitor_list)

    if res:
        monitor_list.remove(res)
        await interaction.response.send_message(f"Removed **_{res['name']}_** from monitoring list.", ephemeral=True)
        target_name = res['URL'].split('/')[-1].replace('.zip', '')
        target_folder = f"./targets/{target_name}"
        if os.path.exists(target_folder):
            try:
                shutil.rmtree(target_folder)
                print(f"Deleted folder: {target_folder}")
            except Exception as e:
                print(f"Error deleting folder {target_folder}: {e}")
                await interaction.response.send_message(f"Failed to delete {target_name}'s folder, please delete it manually.", ephemeral=True)
                return
    else:
        await interaction.response.send_message(f"**_{target}_** not found.", ephemeral=True)


@bot.event
async def on_disconnect():
    save_list()
    print('Bot disconnected, data saved.')

# run bot
bot.run(DISCORD_TOKEN)


# TOKEN = os.getenv('DISCORD_BOT_TOKEN')
# if TOKEN:
#     bot.run(TOKEN)
# else:
#     print("Token not found. Please set the DISCORD_BOT_TOKEN environment variable.")
