#!/usr/bin/env python3
import discord
from discord.ext import commands
import json
import sqlite3
import os
import sys
from PIL import Image, ImageDraw
import requests
from io import BytesIO

with open("config.json") as f:
    config = json.load(f)

intents = discord.Intents.default()
intents.members = True
intents.guilds = True

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
    avatar = avatar.resize((140, 140), Image.LANCZOS)
    draw = ImageDraw.Draw(avatar)
    draw.rectangle([0, 0, 139, 139], outline=(0, 255, 0, 200), width=2)
    gif = Image.open(gif_path)
    frames = []
    x = config["face_position"]["x"]
    y = config["face_position"]["y"]
    try:
        while True:
            frame = gif.copy().convert("RGBA")
            mask = Image.new("L", avatar.size, 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse([5, 5, 134, 134], fill=255)
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
    msg = (
        f"{member.mention} Wellcome to \U0001d400\U0001d40a\U0001d41e\U0001d41c \U0001d41a\U0001d41c\U0001d42b\U0001d41e\U0001d42b\n"
        f"do 3invite for the free tool\n"
        f"(invited by {inviter_name})\n"
        f"(member count {total})"
    )
    await channel.send(msg)
    avatar_url = member.display_avatar.url
    gif_result = make_profile_gif(avatar_url)
    if gif_result and os.path.exists(gif_result):
        with open(gif_result, "rb") as f:
            await channel.send(file=discord.File(f, filename="welcome.gif"))
        os.remove(gif_result)

if __name__ == "__main__":
    if not os.path.exists("1.gif"):
        print("[-] 1.gif NOT FOUND")
        sys.exit(1)
    bot.run(config["token"])
