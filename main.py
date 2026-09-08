import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
import logging

# ---------- LOGGING (βοηθάει να δεις τι έγινε στα Railway logs) ----------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("discord-bot")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

WELCOME_CHANNEL_NAME = "welcome"  # άλλαξέ το αν έχεις άλλο όνομα
TICKET_CATEGORY_NAME = "Tickets"


@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user}")
    try:
        await bot.tree.sync()
    except Exception as e:
        log.error(f"Command sync failed: {e}")


# ---------- Πιάνει ΟΠΟΙΟΔΗΠΟΤΕ σφάλμα σε events, ώστε να μην κολλάει/πέφτει το bot ----------
@bot.event
async def on_error(event_method, *args, **kwargs):
    log.exception(f"Unhandled error in event: {event_method}")


# ---------- Πιάνει σφάλματα σε commands (π.χ. /setup-tickets) ----------
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    log.exception(f"App command error: {error}")
    try:
        if interaction.response.is_done():
            await interaction.followup.send("Κάτι πήγε στραβά, δοκίμασε ξανά.", ephemeral=True)
        else:
            await interaction.response.send_message("Κάτι πήγε στραβά, δοκίμασε ξανά.", ephemeral=True)
    except Exception:
        pass


@bot.event
async def on_member_join(member):
    try:
        channel = discord.utils.get(member.guild.text_channels, name=WELCOME_CHANNEL_NAME)
        if channel:
            embed = discord.Embed(
                title=f"Καλωσόρισες, {member.name}! 👋",
                description="Ρίξε μια ματιά στα κανάλια μας και δες τι προσφέρουμε.",
                color=discord.Color.purple()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await channel.send(embed=embed)
    except Exception as e:
        log.error(f"Welcome message failed: {e}")


class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Άνοιγμα Ticket", style=discord.ButtonStyle.blurple, custom_id="open_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
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
        except Exception as e:
            log.error(f"Ticket creation failed: {e}")
            try:
                await interaction.response.send_message("Κάτι πήγε στραβά, δοκίμασε ξανά.", ephemeral=True)
            except Exception:
                pass


class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Κλείσιμο Ticket", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.send_message("Κλείνει το ticket σε 3 δευτερόλεπτα...")
            await interaction.channel.send("👋")
            await asyncio.sleep(3)
            await interaction.channel.delete()
        except Exception as e:
            log.error(f"Ticket close failed: {e}")


@bot.tree.command(name="setup-tickets", description="Στέλνει το μήνυμα για άνοιγμα ticket")
async def setup_tickets(interaction: discord.Interaction):
    try:
        embed = discord.Embed(
            title="🎫 Χρειάζεσαι βοήθεια;",
            description="Πάτησε το κουμπί παρακάτω για να ανοίξεις ticket.",
            color=discord.Color.blurple()
        )
        await interaction.channel.send(embed=embed, view=TicketView())
        await interaction.response.send_message("Έτοιμο!", ephemeral=True)
    except Exception as e:
        log.error(f"Setup-tickets failed: {e}")


# ---------- Auto-reconnect: αν κοπεί η σύνδεση, ξαναπροσπαθεί μόνο του ----------
async def main():
    while True:
        try:
            await bot.start(os.environ["TOKEN"])
        except discord.errors.ConnectionClosed:
            log.warning("Connection closed, reconnecting in 5s...")
            await asyncio.sleep(5)
        except Exception as e:
            log.error(f"Bot crashed: {e}, restarting in 5s...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
