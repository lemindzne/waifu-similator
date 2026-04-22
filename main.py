import discord
import os
import asyncio
import traceback
import sys
from dotenv import load_dotenv
from discord.ext import commands
from database import BotDatabase

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Gắn database vào bot để dùng ở các Cogs
bot.db = BotDatabase("database.db")

async def load_extensions():
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            await bot.load_extension(f'cogs.{filename[:-3]}')
            print(f'✅ Loaded Cog: {filename}')
            
@bot.event
async def on_command_error(ctx, error):
    # 1. Lỗi chưa nhập đủ tham số (ví dụ: !flip mà không nhập tiền)
    if isinstance(error, commands.MissingRequiredArgument):
        return await ctx.send(f"❌ Thiếu tham số rồi! Cách dùng: `{ctx.prefix}{ctx.command.name} [tham số]`")

    # 2. Lỗi nhập sai kiểu dữ liệu (ví dụ: !flip abc thay vì số)
    elif isinstance(error, commands.BadArgument):
        return await ctx.send("❌ Tham số không hợp lệ! Vui lòng kiểm tra lại (ví dụ: phải là số).")

    # 3. Lỗi không tìm thấy lệnh
    elif isinstance(error, commands.CommandNotFound):
        return # Có thể bỏ qua để tránh spam khi người dùng gõ nhầm

    # 4. LỖI LOGIC TRONG CODE (Đây là cái bạn cần nhất để fix)
    else:
        # In lỗi chi tiết ra Console để bạn nhìn thấy dòng bị sai
        print(f'❌ Lỗi xảy ra tại lệnh {ctx.command}:', file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
        
        # Gửi thông báo lên Discord
        await ctx.send(f"⚠️ **Có lỗi hệ thống:** `{error}`")

async def main():
    async with bot:
        await bot.db.create_tables()
        await load_extensions()
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
