import discord
from discord.ext import commands
import random

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def work(self, ctx):
        # Giả sử lấy data từ DB ở đây
        income = random.randint(100, 500)
        
        # Ví dụ check skill đơn giản (nếu có Don Quixote)
        # if user_waifu == "Don Quixote": income *= 1.15
        
        await ctx.send(f"💰 Bạn đã làm việc và nhận được **{income} xu**!")

    @commands.command()
    async def flip(self, ctx, bet: int):
        # Logic đánh bạc đã bàn ở trên
        result = random.choice(["Thắng", "Thua"])
        await ctx.send(f"Kết quả là: **{result}**")

async def setup(bot):
    await bot.add_cog(Economy(bot))
