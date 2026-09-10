import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
import logging

# ---------- LOGGING ----------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("discord-bot")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

WELCOME_CHANNEL_NAME = "welcome"
TICKET_CATEGORY_NAME = "Tickets"
REVIEWS_CHANNEL_NAME = "reviews"
BANNER_URL = "https://github.com/user-attachments/assets/e98f3479-aad4-46fb-9ecb-d9950ee50265"


@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user}")
    try:
        bot.add_view(SupportTicketView())
        bot.add_view(BuyTicketView())
        bot.add_view(CloseTicketView())
    except Exception as e:
        log.error(f"Persistent view registration failed: {e}")
    try:
        await bot.tree.sync()
    except Exception as e:
        log.error(f"Command sync failed: {e}")


@bot.event
async def on_error(event_method, *args, **kwargs):
    log.exception(f"Unhandled error in event: {event_method}")


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
        channel = discord.utils.find(
            lambda c: WELCOME_CHANNEL_NAME in c.name.lower(), member.guild.text_channels
        )
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


# ---------------- TICKETS ----------------

async def create_ticket_channel(interaction: discord.Interaction, ticket_type: str, emoji: str):
    try:
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)
        if not category:
            category = await guild.create_category(TICKET_CATEGORY_NAME)

        channel_name = f"{ticket_type}-{interaction.user.name}".lower()
        existing = discord.utils.get(guild.text_channels, name=channel_name)
        if existing:
            await interaction.response.send_message("Έχεις ήδη ανοιχτό ticket!", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        channel = await guild.create_text_channel(
            channel_name, category=category, overwrites=overwrites,
            topic=str(interaction.user.id)
        )
        label = "Support" if ticket_type == "support" else "Buy"
        await channel.send(
            f"{emoji} {interaction.user.mention} Άνοιξες **{label} Ticket**. Ένα μέλος του staff θα σε βοηθήσει σύντομα!",
            view=CloseTicketView()
        )
        await interaction.response.send_message(f"Ticket δημιουργήθηκε: {channel.mention}", ephemeral=True)
    except Exception as e:
        log.error(f"Ticket creation failed: {e}")
        try:
            await interaction.response.send_message("Κάτι πήγε στραβά, δοκίμασε ξανά.", ephemeral=True)
        except Exception:
            pass


class SupportTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Support", emoji="📞", style=discord.ButtonStyle.secondary, custom_id="open_ticket_support")
    async def open_support_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await create_ticket_channel(interaction, "support", "📞")


class BuyTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Buy", emoji="🛒", style=discord.ButtonStyle.secondary, custom_id="open_ticket_buy")
    async def open_buy_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await create_ticket_channel(interaction, "buy", "🛒")


class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Κλείσιμο Ticket", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            channel = interaction.channel
            opener_id = int(channel.topic) if channel.topic and channel.topic.isdigit() else None

            await interaction.response.send_message("Κλείνει το ticket...")

            if opener_id:
                embed = discord.Embed(
                    title="⭐ Βαθμολόγησε την εξυπηρέτηση",
                    description="Πριν κλείσει το ticket, πες μας πώς πήγε! (μόνο ο πελάτης μπορεί να απαντήσει)",
                    color=discord.Color.blue()
                )
                await channel.send(embed=embed, view=RatingView(opener_id, channel))
            else:
                await channel.send("👋")
                await asyncio.sleep(3)
                await channel.delete()
        except Exception as e:
            log.error(f"Ticket close failed: {e}")


class RatingView(discord.ui.View):
    def __init__(self, opener_id: int, ticket_channel: discord.TextChannel):
        super().__init__(timeout=60)
        self.opener_id = opener_id
        self.ticket_channel = ticket_channel
        self.rating = None
        for i in range(1, 6):
            self.add_item(StarButton(i))

    async def on_timeout(self):
        try:
            await self.ticket_channel.send("⏱️ Ο χρόνος για αξιολόγηση έληξε, κλείνει το ticket.")
            await asyncio.sleep(2)
            await self.ticket_channel.delete()
        except Exception as e:
            log.error(f"Rating timeout close failed: {e}")


class StarButton(discord.ui.Button):
    def __init__(self, value: int):
        super().__init__(label="⭐" * value, style=discord.ButtonStyle.secondary, custom_id=f"star_{value}")
        self.value = value

    async def callback(self, interaction: discord.Interaction):
        view: RatingView = self.view
        if interaction.user.id != view.opener_id:
            await interaction.response.send_message("Μόνο ο πελάτης που άνοιξε το ticket μπορεί να αξιολογήσει.", ephemeral=True)
            return

        view.rating = self.value
        await interaction.response.send_modal(ReviewModal(view))


class ReviewModal(discord.ui.Modal, title="Άφησε ένα σχόλιο (προαιρετικό)"):
    comment = discord.ui.TextInput(
        label="Σχόλιο",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=300,
        placeholder="Πώς ήταν η εμπειρία σου; (προαιρετικό)"
    )

    def __init__(self, view: RatingView):
        super().__init__()
        self.rating_view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            guild = interaction.guild
            reviews_channel = discord.utils.find(
                lambda c: REVIEWS_CHANNEL_NAME in c.name.lower(), guild.text_channels
            )
            if not reviews_channel:
                reviews_channel = await guild.create_text_channel(REVIEWS_CHANNEL_NAME)

            stars = "⭐" * self.rating_view.rating + "☆" * (5 - self.rating_view.rating)
            embed = discord.Embed(
                title="Νέο Review",
                description=f"{stars}\n\n{self.comment.value or '*Χωρίς σχόλιο*'}",
                color=discord.Color.blue()
            )
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            await reviews_channel.send(embed=embed)

            await interaction.response.send_message("Ευχαριστούμε για την αξιολόγηση! 🙏", ephemeral=True)

            await interaction.channel.send("✅ Ευχαριστούμε! Το ticket κλείνει σε λίγο...")
            await asyncio.sleep(3)
            await interaction.channel.delete()
        except Exception as e:
            log.error(f"Review submit failed: {e}")


@bot.tree.command(name="setup-tickets", description="Στέλνει το μήνυμα για άνοιγμα ticket")
async def setup_tickets(interaction: discord.Interaction):
    try:
        main_embed = discord.Embed(
            title="🎫 NexaServices Tickets",
            description=(
                "Need assistance? Choose a category below to open a "
                "ticket — our staff team will assist you shortly!"
            ),
            color=discord.Color.blue()
        )
        main_embed.set_image(url=BANNER_URL)
        main_embed.set_footer(text="NexaServices | All rights reserved")

        await interaction.channel.send(embed=main_embed)

        support_embed = discord.Embed(
            description=(
                "📞 __**Support Ticket**__\n"
                "If you need help, have a problem, need a replacement, or "
                "have won a reward, click here to open a Support ticket "
                "and our staff will assist you shortly."
            ),
            color=discord.Color.blue()
        )
        await interaction.channel.send(embed=support_embed, view=SupportTicketView())

        buy_embed = discord.Embed(
            description=(
                "🛒 __**Buy Ticket**__\n"
                "Looking to make a purchase? Open a Buy ticket and our "
                "team will guide you through your order."
            ),
            color=discord.Color.blue()
        )
        await interaction.channel.send(embed=buy_embed, view=BuyTicketView())

        await interaction.response.send_message("Έτοιμο!", ephemeral=True)
    except Exception as e:
        log.error(f"Setup-tickets failed: {e}")


# ---------- Auto-reconnect ----------
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
