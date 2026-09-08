import discord
from discord.ext import commands
from discord import app_commands
import os

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

WELCOME_CHANNEL_NAME = "welcome"  # άλλαξέ το αν έχεις άλλο όνομα
TICKET_CATEGORY_NAME = "Tickets"

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.tree.sync()

@bot.event
async def on_member_join(member):
    channel = discord.utils.get(member.guild.text_channels, name=WELCOME_CHANNEL_NAME)
    if channel:
        embed = discord.Embed(
            title=f"Καλωσόρισες, {member.name}! 👋",
            description="Ρίξε μια ματιά στα κανάλια μας και δες τι προσφέρουμε.",
            color=discord.Color.purple()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await channel.send(embed=embed)

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Άνοιγμα Ticket", style=discord.ButtonStyle.blurple, custom_id="open_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)
        if not category:
            category = await guild.create_category(TICKET_CATEGORY_NAME)

        existing = discord.utils.get(guild.text_channels, name=f"ticket-{interaction.user.name}".lower())
        if existing:
            await interaction.response.send_message("Έχεις ήδη ανοιχτό ticket!", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        channel = await guild.create_text_channel(
            f"ticket-{interaction.user.name}", category=category, overwrites=overwrites
        )
        await channel.send(f"{interaction.user.mention} Ένα μέλος του staff θα σε βοηθήσει σύντομα!",
                            view=CloseTicketView())
        await interaction.response.send_message(f"Ticket δημιουργήθηκε: {channel.mention}", ephemeral=True)

class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Κλείσιμο Ticket", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Κλείνει το ticket σε 3 δευτερόλεπτα...")
        await interaction.channel.send("👋")
        import asyncio
        await asyncio.sleep(3)
        await interaction.channel.delete()

@bot.tree.command(name="setup-tickets", description="Στέλνει το μήνυμα για άνοιγμα ticket")
async def setup_tickets(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎫 Χρειάζεσαι βοήθεια;",
        description="Πάτησε το κουμπί παρακάτω για να ανοίξεις ticket.",
        color=discord.Color.blurple()
    )
    await interaction.channel.send(embed=embed, view=TicketView())
    await interaction.response.send_message("Έτοιμο!", ephemeral=True)

bot.run(os.environ["TOKEN"])
