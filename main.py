import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import random
from datetime import datetime

# Не забудьте захистити свій токен (наприклад, через змінні середовища або файл конфігурації)
TOKEN = os.getenv("DISCORD_TOKEN")
LOG_CHANNEL_ID = 1299805349808836618  # Лог-канал (для інших повідомлень)
MODERATOR_ROLE = "Модератор"
DATA_FILE = "mod_data.json"

WELCOME_CHANNEL_ID = 1359540425429487627
LEAVE_CHANNEL_ID = 1359652835045937303

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

join_times = {}

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
else:
    data = {}


def save():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


def is_mod(member):
    return any(role.name == MODERATOR_ROLE for role in member.roles)


async def dm(member, text):
    try:
        await member.send(text)
    except Exception as e:
        print(f"❌ Не вдалося надіслати DM до {member}: {e}")


async def log_to_channel(guild, text):
    channel = guild.get_channel(LOG_CHANNEL_ID)
    if channel:
        await channel.send(text)


@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Бот {bot.user} запущено та slash-команди синхронізовано")


@bot.event
async def on_member_join(member):
    guild = member.guild
    welcome_channel = guild.get_channel(WELCOME_CHANNEL_ID)
    # Надсилаємо привітання в канал привітання (тільки ID і тег)
    embed = discord.Embed(
        title="👋 Новий учасник!",
        description=f"{member.mention} приєднався до сервера!",
        color=random.randint(0, 0xFFFFFF))
    if welcome_channel:
        await welcome_channel.send(embed=embed)
    # Надсилаємо особисте повідомлення новому учаснику (повний текст)
    await dm(
        member, f"Вітаємо {member.mention} в нашому клані! "
        f"Щоб розпочати приймати участь ознайомтесь з правилами клану <#1297650987606999181>.\n"
        f"Ознайомились? Тепер подайте на роль <#1267076896789762140>.\n\n"
        f"Приклад:\n"
        f"Станіслав Флібюстер (нік)\n"
        f"1347 (ід)\n"
        f"Александр Андр (той хто вас запросив)")
    join_times[member.id] = datetime.utcnow()


@bot.event
async def on_member_remove(member):
    guild = member.guild
    leave_channel = guild.get_channel(LEAVE_CHANNEL_ID)
    join_time = join_times.pop(member.id, None)
    time_spent = "невідомо"
    if join_time:
        time_spent = str(datetime.utcnow() - join_time).split('.')[0]
    # Тепер використовується member.mention для тегання користувача
    msg = f"👋 {member.mention} покинув сервер. Провів на сервері: {time_spent}"
    if leave_channel:
        await leave_channel.send(msg)


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    await bot.process_commands(message)


@tree.command(
    name="announce",
    description="Розіслати повідомлення в особисті учасникам з до 5 ролей")
@app_commands.describe(message="Повідомлення для надсилання",
                       role1="Роль 1",
                       role2="Роль 2",
                       role3="Роль 3",
                       role4="Роль 4",
                       role5="Роль 5")
async def announce(interaction: discord.Interaction,
                   message: str,
                   role1: discord.Role = None,
                   role2: discord.Role = None,
                   role3: discord.Role = None,
                   role4: discord.Role = None,
                   role5: discord.Role = None):
    if not is_mod(interaction.user):
        return await interaction.response.send_message("❌ У тебе немає прав",
                                                       ephemeral=True)

    roles = [role for role in [role1, role2, role3, role4, role5] if role]
    if not roles:
        return await interaction.response.send_message(
            "❌ Не вказано жодної ролі.", ephemeral=True)

    sent_count = 0
    failed_count = 0
    members_sent = set()

    for role in roles:
        for member in role.members:
            if member.bot or member in members_sent:
                continue
            try:
                await member.send(f"📢 **Оголошення:** {message}")
                sent_count += 1
                members_sent.add(member)
            except discord.Forbidden:
                failed_count += 1
            except Exception as e:
                print(f"❌ Помилка при надсиланні до {member}: {e}")
                failed_count += 1

    await interaction.response.send_message(
        f"✅ Оголошення розіслано.\n📨 Успішно: {sent_count}\n❌ Не вдалося: {failed_count}",
        ephemeral=True)


@tree.command(name="ban", description="Забанити учасника")
@app_commands.describe(member="Учасник", reason="Причина")
async def ban(interaction: discord.Interaction,
              member: discord.Member,
              reason: str = "Без причини"):
    if not is_mod(interaction.user):
        return await interaction.response.send_message("❌ У тебе немає прав",
                                                       ephemeral=True)
    await member.ban(reason=reason)
    await dm(member, f"❌ Тебе забанено на сервері. Причина: {reason}")
    await log_to_channel(interaction.guild,
                         f"{member.mention} був забанений. Причина: {reason}")
    await interaction.response.send_message("✅ Учасника забанено.",
                                            ephemeral=True)


@tree.command(name="mute", description="Зам'ютити учасника")
@app_commands.describe(member="Учасник", reason="Причина")
async def mute(interaction: discord.Interaction,
               member: discord.Member,
               reason: str = "Без причини"):
    if not is_mod(interaction.user):
        return await interaction.response.send_message("❌ У тебе немає прав",
                                                       ephemeral=True)
    muted_role = discord.utils.get(interaction.guild.roles, name="Muted")
    if not muted_role:
        muted_role = await interaction.guild.create_role(name="Muted")
        for channel in interaction.guild.channels:
            await channel.set_permissions(muted_role,
                                          speak=False,
                                          send_messages=False)
    await member.add_roles(muted_role)
    await dm(member, f"🔇 Тебе зам'ютили. Причина: {reason}")
    await log_to_channel(
        interaction.guild,
        f"{member.mention} був зам'ючений. Причина: {reason}")
    await interaction.response.send_message("✅ Учасника зам'ючено.",
                                            ephemeral=True)


@tree.command(name="warn", description="Видати попередження користувачу")
@app_commands.describe(member="Учасник", reason="Причина")
async def warn(interaction: discord.Interaction,
               member: discord.Member,
               reason: str = "Без причини"):
    if not is_mod(interaction.user):
        return await interaction.response.send_message("❌ У тебе немає прав",
                                                       ephemeral=True)
    await interaction.response.defer(thinking=False, ephemeral=True)
    uid = str(member.id)
    data.setdefault(uid, {"warn": 0, "reprimand": 0})
    data[uid]["warn"] += 1
    await dm(member, f"⚠️ Ти отримав попередження. Причина: {reason}")
    await log_to_channel(
        interaction.guild,
        f"{member.mention} отримав попередження. Причина: {reason}")
    if data[uid]["warn"] >= 2:
        data[uid]["warn"] = 0
        data[uid]["reprimand"] += 1
        await dm(member, "⛔️ Автоматична догана за 2 попередження.")
        await log_to_channel(
            interaction.guild,
            f"{member.mention} автоматично отримав догану за 2 попередження.")
    if data[uid]["reprimand"] >= 3:
        await dm(member, "❌ Тебе вигнано з сервера за 3 догани.")
        await log_to_channel(
            interaction.guild,
            f"{member.mention} вигнано з сервера за 3 догани.")
        await member.kick(reason="3 догани")
        data.pop(uid)
    save()
    await interaction.followup.send("✅ Готово.", ephemeral=True)


@tree.command(name="reprimand", description="Видати догану користувачу")
@app_commands.describe(member="Учасник", reason="Причина")
async def reprimand(interaction: discord.Interaction,
                    member: discord.Member,
                    reason: str = "Без причини"):
    if not is_mod(interaction.user):
        return await interaction.response.send_message("❌ У тебе немає прав",
                                                       ephemeral=True)
    await interaction.response.defer(thinking=False, ephemeral=True)
    uid = str(member.id)
    data.setdefault(uid, {"warn": 0, "reprimand": 0})
    data[uid]["reprimand"] += 1
    await dm(member, f"⛔️ Ти отримав догану. Причина: {reason}")
    await log_to_channel(
        interaction.guild,
        f"{member.mention} отримав догану. Причина: {reason}")
    if data[uid]["reprimand"] >= 3:
        await dm(member, "❌ Тебе вигнано з сервера за 3 догани.")
        await log_to_channel(
            interaction.guild,
            f"{member.mention} вигнано з сервера за 3 догани.")
        await member.kick(reason="3 догани")
        data.pop(uid)
    save()
    await interaction.followup.send("✅ Готово.", ephemeral=True)


@tree.command(name="removewarn", description="Зняти попередження з учасника")
@app_commands.describe(member="Учасник", reason="Причина")
async def removewarn(interaction: discord.Interaction,
                     member: discord.Member,
                     reason: str = "Без причини"):
    if not is_mod(interaction.user):
        return await interaction.response.send_message("❌ У тебе немає прав",
                                                       ephemeral=True)
    await interaction.response.defer(thinking=False, ephemeral=True)
    uid = str(member.id)
    if uid in data and data[uid]["warn"] > 0:
        data[uid]["warn"] -= 1
        await dm(member, f"✅ З вас знято попередження. Причина: {reason}")
        await log_to_channel(
            interaction.guild,
            f"{member.mention} — попередження знято. Причина: {reason}")
        save()
        await interaction.followup.send("✅ Готово.", ephemeral=True)
    else:
        await interaction.followup.send("❌ У користувача немає попереджень.",
                                        ephemeral=True)


@tree.command(name="removereprimand", description="Зняти догану з учасника")
@app_commands.describe(member="Учасник", reason="Причина")
async def removereprimand(interaction: discord.Interaction,
                          member: discord.Member,
                          reason: str = "Без причини"):
    if not is_mod(interaction.user):
        return await interaction.response.send_message("❌ У тебе немає прав",
                                                       ephemeral=True)
    await interaction.response.defer(thinking=False, ephemeral=True)
    uid = str(member.id)
    if uid in data and data[uid]["reprimand"] > 0:
        data[uid]["reprimand"] -= 1
        await dm(member, f"✅ З вас знято догану. Причина: {reason}")
        await log_to_channel(
            interaction.guild,
            f"{member.mention} — догана знята. Причина: {reason}")
        save()
        await interaction.followup.send("✅ Готово.", ephemeral=True)
    else:
        await interaction.followup.send("❌ У користувача немає доган.",
                                        ephemeral=True)


@tree.command(name="reset", description="Обнулити статус учасника")
@app_commands.describe(member="Учасник")
async def reset(interaction: discord.Interaction, member: discord.Member):
    if not is_mod(interaction.user):
        return await interaction.response.send_message("❌ У тебе немає прав",
                                                       ephemeral=True)
    await interaction.response.defer(thinking=False, ephemeral=True)
    uid = str(member.id)
    data[uid] = {"warn": 0, "reprimand": 0}
    await dm(member, "⚠️ Всі попередження та догани було обнулено.")
    await log_to_channel(interaction.guild,
                         f"{member.mention} — статус обнулено.")
    save()
    await interaction.followup.send("✅ Готово.", ephemeral=True)


@tree.command(
    name="listpunishments",
    description="Показати всіх користувачів з попередженнями та доганами")
async def listpunishments(interaction: discord.Interaction):
    if not is_mod(interaction.user):
        return await interaction.response.send_message("❌ У тебе немає прав",
                                                       ephemeral=True)
    await interaction.response.defer(thinking=False, ephemeral=True)
    if not data:
        await log_to_channel(
            interaction.guild,
            "✅ Немає користувачів з попередженнями або доганами.")
        return await interaction.followup.send("✅ Немає записів.",
                                               ephemeral=True)
    result = ""
    for uid, record in data.items():
        warn = record.get("warn", 0)
        reprimand = record.get("reprimand", 0)
        if warn > 0 or reprimand > 0:
            member = interaction.guild.get_member(int(uid))
            name = member.mention if member else f"`{uid}`"
            result += f"{name}: ⚠️ {warn} попереджень, ⛔ {reprimand} доган\n"
    if result:
        await log_to_channel(interaction.guild,
                             "📋 Список користувачів з порушеннями:\n" + result)
        await interaction.followup.send("📨 Надіслано в лог-канал.",
                                        ephemeral=True)
    else:
        await log_to_channel(
            interaction.guild,
            "✅ У жодного учасника немає попереджень або доганами.")
        await interaction.followup.send("✅ Усі чисті.", ephemeral=True)


def run_web():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

# Запускаємо веб-сервер у фоновому потоці для Railway
threading.Thread(target=run_web).start()

# Запускаємо Discord-бота
bot.run(TOKEN)
