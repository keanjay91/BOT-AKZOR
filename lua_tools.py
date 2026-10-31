import re
import base64
import aiohttp
import discord
from discord.ext import commands

def setup_lua_tools(bot, ch_cek, ch_obf, ch_deobf, ch_bypass):
    def is_cek(c): return c.id == ch_cek
    def is_obf(c): return c.id == ch_obf
    def is_deobf(c): return c.id == ch_deobf
    def is_bypass(c): return c.id == ch_bypass

    def scan_lua(kode: str):
        decoded_text = kode
        hex_matches = re.findall(r"'([0-9a-fA-F]{10,})'", kode)
        for h in hex_matches:
            try: decoded_text += "\n" + bytes.fromhex(h).decode('utf-8', errors='ignore')
            except: pass

        b64_matches = re.findall(r"'([A-Za-z0-9+/=]{10,})'", kode)
        for b in b64_matches:
            try: decoded_text += "\n" + base64.b64decode(b).decode('utf-8', errors='ignore')
            except: pass

        suspicious = []
        if "loadstring" in decoded_text: suspicious.append("`loadstring` (Eval)")
        if "require" in decoded_text: suspicious.append("`require` (Module)")
        if "io." in decoded_text: suspicious.append("`io.` (File I/O)")
        if "os." in decoded_text: suspicious.append("`os.` (System OS)")
        if "getfenv" in decoded_text or "setfenv" in decoded_text: suspicious.append("`getfenv/setfenv`")
        
        return suspicious

    @bot.event
    async def on_message(message: discord.Message):
        if message.author == bot.user: return

        if is_cek(message.channel) and message.attachments:
            for attachment in message.attachments:
                if attachment.filename.endswith((".lua", ".txt")):
                    await message.reply(f"⏳ Ngecek file `{attachment.filename}`...")
                    try:
                        kode_bytes = await attachment.read()
                        kode = kode_bytes.decode('utf-8', errors='ignore')
                    except Exception as e:
                        await message.reply(f"❌ Gagal baca file: {e}")
                        continue

                    baris = len(kode.splitlines())
                    suspicious = scan_lua(kode)

                    embed = discord.Embed(title=f"🔍 Analisa File: {attachment.filename}", color=0x3498DB)
                    embed.add_field(name="📝 Info File", value=f"Baris: **{baris}**", inline=False)
                    
                    if suspicious:
                        embed.add_field(name="⚠️ Fungsi Mencurigakan", value="\n".join(suspicious), inline=False)
                        embed.color = 0xE74C3C 
                    else:
                        embed.add_field(name="✅ Status", value="Gak ada fungsi mencurigakan.", inline=False)
                    await message.reply(embed=embed)
            return
        await bot.process_commands(message)

    @bot.command(name="obfuscate")
    async def obfuscate(ctx: commands.Context, *, kode: str = ""):
        if not is_obf(ctx.channel): return
        if not kode: return await ctx.reply("Masukin kode Lua-nya.")
        fake_obf = f"-- OBF\nlocal _0x = '{kode.encode('utf-8').hex()}'\nloadstring(_0x)()"
        await ctx.reply(f"🔒 **Hasil:**\n```lua\n{fake_obf}\n```")

    @bot.command(name="deobfuscate")
    async def deobfuscate(ctx: commands.Context, *, kode: str = ""):
        if not is_deobf(ctx.channel): return
        if not kode: return await ctx.reply("Masukin kode obfuscate-nya.")
        
        hasil = "Mencoba bongkar obfuscate...\n\n"
        hex_matches = re.findall(r"'([0-9a-fA-F]+)'", kode)
        if hex_matches:
            hasil += "**Terdeteksi Hex String:**\n"
            for h in hex_matches[:3]:
                try: hasil += f"`{h}` -> `{bytes.fromhex(h).decode('utf-8', errors='ignore')}`\n"
                except: pass
        
        await ctx.reply(f"🔓 **Hasil Analisa:**\n{hasil[:1900]}")

    @bot.command(name="bypass")
    async def bypass_url(ctx: commands.Context, url: str = ""):
        if not is_bypass(ctx.channel): return
        if not url.startswith("http"): return await ctx.reply("Masukin link yang bener.")
        
        msg = await ctx.reply(f"⏳ Nge-bypass {url}...")
        api_url = f"https://api.bypass.vip/bypass?url={url}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, timeout=15) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        hasil = data.get("result", "")
                        if not hasil or "shut down" in hasil.lower():
                            await msg.edit(content="❌ API down/limit.")
                        else:
                            await msg.edit(content=f"✅ **Link:** {hasil}")
                    else:
                        await msg.edit(content="❌ Gagal.")
        except Exception as e: await msg.edit(content=f"❌ Error: {e}")
