#!/usr/bin/env python3
import discord
from discord.ext import commands
from discord import app_commands
import json
import sqlite3
import os
import sys
from PIL import Image, ImageDraw
import requests
from io import BytesIO
import asyncio

with open("config.json") as f:
    config = json.load(f)

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

conn = sqlite3.connect("invites.db")
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS inviters (
    invited_id INTEGER PRIMARY KEY,
    inviter_id INTEGER
)""")
conn.commit()

def make_profile_gif(avatar_url, gif_path="1.gif", output_path="welcome.gif"):
    try:
        resp = requests.get(avatar_url, stream=True, timeout=10)
        avatar = Image.open(BytesIO(resp.content)).convert("RGBA")
    except:
        return None

    # Avatar-Größe aus config
    aw = config.get("avatar_size", {}).get("width", 140)
    ah = config.get("avatar_size", {}).get("height", 146)
    avatar = avatar.resize((aw, ah), Image.LANCZOS)

    # Runden Rahmen zeichnen
    draw = ImageDraw.Draw(avatar)
    draw.rectangle([0, 0, aw - 1, ah - 1], outline=(0, 255, 0, 200), width=2)

    gif = Image.open(gif_path)
    frames = []
    x = config["face_position"]["x"]
    y = config["face_position"]["y"]
    try:
        while True:
            frame = gif.copy().convert("RGBA")
            # Runde Maske für den Avatar
            mask = Image.new("L", avatar.size, 0)
            mask_draw = ImageDraw.Draw(mask)
            margin = 5
            mask_draw.ellipse([margin, margin, aw - 1 - margin, ah - 1 - margin], fill=255)
            avatar_cropped = Image.new("RGBA", avatar.size, (0, 0, 0, 0))
            avatar_cropped.paste(avatar, (0, 0), mask)
            frame.paste(avatar_cropped, (x, y), avatar_cropped)
            frames.append(frame)
            gif.seek(gif.tell() + 1)
    except EOFError:
        pass
    if not frames:
        return None
    frames[0].save(output_path, save_all=True, append_images=frames[1:],
                   loop=0, duration=gif.info.get("duration", 100), disposal=2)
    return output_path

async def get_inviter(member):
    c.execute("SELECT inviter_id FROM inviters WHERE invited_id=?", (member.id,))
    result = c.fetchone()
    if result:
        inviter = member.guild.get_member(result[0])
        if inviter:
            return inviter
    try:
        async for entry in member.guild.audit_logs(limit=5, action=discord.AuditLogAction.invite_create):
            if entry.target:
                return entry.user
    except:
        pass
    return None

@bot.event
async def on_ready():
    print(f"[+] BOT ONLINE: {bot.user}")
    guild = bot.get_guild(config["guild_id"])
    if guild:
        print(f"[+] SERVER: {guild.name} | MEMBERS: {guild.member_count}")
    try:
        await bot.tree.sync()
        print("[+] Slash-Commands synced")
    except Exception as e:
        print(f"[-] Slash-Command sync failed: {e}")

@bot.event
async def on_member_join(member):
    if member.guild.id != config["guild_id"]:
        return
    channel = bot.get_channel(config["welcome_channel_id"])
    if not channel:
        return
    inviter = await get_inviter(member)
    inviter_name = inviter.display_name if inviter else "Unknown"
    if inviter:
        c.execute("INSERT OR REPLACE INTO inviters VALUES (?,?)",
                   (member.id, inviter.id))
        conn.commit()
    total = member.guild.member_count

    # Nachricht senden
    msg = (
        f"{member.mention} Welcome to 𝐀𝐪𝐮𝐚 𝐌𝐚𝐫𝐤𝐞𝐭💧\n"
        f"𝘿𝙊 3 𝙄𝙉𝙑𝙄𝙏𝙀𝙎 𝙁𝙊𝙍 𝙏𝙃𝙀 𝙁𝙍𝙀𝙀 𝙏𝙊𝙊𝙇\n"
        f"𝙄𝙣𝙫𝙞𝙩𝙚𝙙 𝙗𝙮 {inviter_name}\n"
        f"𝙈𝙚𝙢𝙗𝙚𝙧 𝘾𝙤𝙪𝙣𝙩 : {total}"
    )
    await channel.send(msg)

    # GIF mit Avatar erstellen und senden (asynchron, nicht blockierend)
    avatar_url = member.display_avatar.url
    gif_result = await asyncio.to_thread(make_profile_gif, avatar_url)
    if gif_result and os.path.exists(gif_result):
        with open(gif_result, "rb") as f:
            await channel.send(file=discord.File(f, filename="welcome.gif"))
        os.remove(gif_result)

# ========== SLASH COMMANDS ==========

@app_commands.default_permissions(administrator=True)
@bot.tree.command(
    name="setup",
    description="Set the current channel as the welcome channel"
)
async def setup(interaction: discord.Interaction):
    config["guild_id"] = interaction.guild_id
    config["welcome_channel_id"] = interaction.channel_id

    with open("config.json", "w") as f:
        json.dump(config, f, indent=4)

    msg = (
        f"Setup complete\n"
        f"Welcome-Channel: {interaction.channel.mention}\n"
        f"Server: {interaction.guild.name} (ID: {interaction.guild_id})\n"
        f"The bot will now greet all new members in this channel."
    )
    await interaction.response.send_message(msg, ephemeral=True)


@app_commands.default_permissions(administrator=True)
@bot.tree.command(
    name="test",
    description="Send a test welcome message"
)
async def test(interaction: discord.Interaction):
    # Defer, damit die Interaktion nicht abläuft (GIF-Erstellung kann dauern)
    await interaction.response.defer(ephemeral=True)

    if "welcome_channel_id" not in config or not config["welcome_channel_id"]:
        await interaction.edit_original_response(
            content="The bot has not been set up yet. Use /setup in the channel you want to use as welcome channel first."
        )
        return

    channel = bot.get_channel(config["welcome_channel_id"])
    if not channel:
        await interaction.edit_original_response(
            content="The saved welcome channel no longer exists. Please run /setup again."
        )
        return

    test_msg = (
        f"{interaction.user.mention} Welcome to 𝐀𝐪𝐮𝐚 𝐌𝐚𝐫𝐤𝐞𝐭💧\n"
        f"𝘿𝙊 3 𝙄𝙉𝙑𝙄𝙏𝙀𝙎 𝙁𝙊𝙍 𝙏𝙃𝙀 𝙁𝙍𝙀𝙀 𝙏𝙊𝙊𝙇\n"
        f"𝙄𝙣𝙫𝙞𝙩𝙚𝙙 𝙗𝙮 Test User\n"
        f"𝙈𝙚𝙢𝙗𝙚𝙧 𝘾𝙤𝙪𝙣𝙩 : {interaction.guild.member_count}"
    )

    await channel.send(test_msg)

    if os.path.exists("1.gif"):
        avatar_url = interaction.user.display_avatar.url
        gif_result = await asyncio.to_thread(make_profile_gif, avatar_url)
        if gif_result and os.path.exists(gif_result):
            with open(gif_result, "rb") as f:
                await channel.send(file=discord.File(f, filename="welcome.gif"))
            os.remove(gif_result)

    await interaction.edit_original_response(
        content=f"Test sent to {channel.mention}"
    )


if __name__ == "__main__":
    if not os.path.exists("1.gif"):
        print("[-] 1.gif NOT FOUND")
        sys.exit(1)
    bot.run(config["MTUwODk4Mjc3OTM5NDY1ODMwNA.GOek05.U5rnqcQopSxDFGqsp1WuVl8DGtna1kVihdop5s"])
