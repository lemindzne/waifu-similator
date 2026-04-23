import discord
from discord.ext import commands
import random
import asyncio
from datetime import datetime, timedelta

class JobSelect(discord.ui.Select):
    def __init__(self, jobs, bot, active_waifu):
        self.jobs = jobs
        self.bot = bot
        self.active_waifu = active_waifu
        
        options = [
            discord.SelectOption(
                label=name, 
                description=f"Lương: {info['min']}-{info['max']} | CD: {info['cd']}h",
                value=name
            ) for name, info in jobs.items()
        ]
        super().__init__(placeholder="Chọn công việc bạn muốn nhận...", options=options)

    async def callback(self, interaction: discord.Interaction):
        try:
            user_id = interaction.user.id
            job_name = self.values[0]
            job_info = self.jobs[job_name]

            # 1. Lấy dữ liệu user (money, active, next_available_str)
            # Ở đây last_work_str đóng vai trò là "thời điểm được làm việc tiếp"
            money, active, next_available_str, level, exp = await self.bot.db.get_user_full(user_id)
            now = datetime.now()

            active_waifu_name = active

            # 2. KIỂM TRA HỒI CHIÊU CHUNG (Global Cooldown)
            if next_available_str:
                next_available = datetime.strptime(next_available_str, '%Y-%m-%d %H:%M:%S')
                if now < next_available:
                    wait_time = next_available - now
                    hours, remainder = divmod(int(wait_time.total_seconds()), 3600)
                    minutes, seconds = divmod(remainder, 60)
                    return await interaction.response.send_message(
                        f"⏳ Bạn đang trong thời gian nghỉ! Hãy nghỉ thêm **{hours}h {minutes}m {seconds}s** nữa để làm việc             tiếp.", 
                        ephemeral=False
                    )

            waifu_cog = self.bot.get_cog("Waifu")
            info = waifu_cog.get_waifu_info(active)
            
            # Lấy giá trị buff từ Dictionary (đã nhân với Level)
            # calculate_bonus trả về con số thực tế (ví dụ: 5.0 hoặc 20.0)
            cd_buff_val = waifu_cog.calculate_bonus(active, level, "work_cd")
            
            base_cd_min = job_info["cd"] * 60 # Chuyển giờ sang phút
            
            if info and info['unit'] == " phút":
                # Trường hợp Ganyu: Trừ thẳng số phút
                total_wait_minutes = max(1, base_cd_min - int(cd_buff_val))
                bonus_cd_display = f"{int(cd_buff_val)}p"
            elif info and info['unit'] == "%":
                # Trường hợp Faust: Giảm theo tỷ lệ %
                # Ví dụ: 20% thì nhân với (1 - 0.2)
                reduction_percent = cd_buff_val / 100
                total_wait_minutes = max(1, int(base_cd_min * (1 - reduction_percent)))
                bonus_cd_display = f"{int(cd_buff_val)}%"
            else:
                # Không có waifu buff CD
                total_wait_minutes = base_cd_min
                bonus_display = "0%"

            # CẬP NHẬT MỐC THỜI GIAN MỚI (Đây là dòng quan trọng nhất)
            new_next_available = now + timedelta(minutes=total_wait_minutes)
            
            # Tính lương (Sử dụng luôn Dictionary cho đồng bộ)
            money_mult = waifu_cog.calculate_bonus(active, level, "work_money")
            income = int(random.randint(job_info["min"], job_info["max"]) * money_mult * (1 + level * 0.02))

            # Tính mốc thời gian ĐƯỢC LÀM VIỆC TIẾP theo công việc vừa chọn
            new_next_available = now + timedelta(minutes=total_wait_minutes)

            # 4. CẬP NHẬT DATABASE
            await self.bot.db.update_money(user_id, income)
            await self.bot.db.update_work_time(user_id, new_next_available.strftime('%Y-%m-%d %H:%M:%S'))

            display_h, display_m = divmod(total_wait_minutes, 60)
            cd_text = f"{display_h}h" if display_m == 0 else f"{display_h}h {display_m}m"

            embed = discord.Embed(title="✅ Nhận việc thành công!", color=discord.Color.green())
            embed.add_field(name="Công việc", value=job_name)
            embed.add_field(name="Tiền lương", value=f"{income:,} xu")
            embed.add_field(name="Thời gian nghỉ", value=f"{cd_text} (Đã giảm {bonus_cd_display})")
            embed.set_footer(text=f"Đã áp dụng buff từ: {active if active else 'Không có'}")

            await interaction.response.edit_message(embed=embed, view=None)
        
        except Exception as e:
            # 1. In lỗi cực kỳ chi tiết ra console để biết sai ở dòng nào
            print(f"❌ [LỖI TƯƠNG TÁC JOB]: {e}")
            import traceback
            traceback.print_exc() 

            # 2. Phản hồi lại Discord để không hiện "Tương tác không thành công"
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Có lỗi khi nhận việc: `{e}`", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ Có lỗi xảy ra: `{e}`", ephemeral=True)

class JobView(discord.ui.View):
    def __init__(self, jobs, bot, active_waifu, author):
        super().__init__()
        self.author = author
        self.add_item(JobSelect(jobs, bot, active_waifu))
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Nếu người bấm không phải là người gọi lệnh
        if interaction.user.id != self.author.id:
            # Gửi thông báo ẩn chỉ người đó thấy
            await interaction.response.send_message(
                f"❌ Menu này dành cho {self.author.name}, không phải bạn!", 
                ephemeral=True
            )
            return False # Ngăn không cho chạy tiếp callback
        return True

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.jobs = {
            "Giao báo": {"min": 100, "max": 300, "cd": 1, "desc": "Giao báo buổi sáng quanh khu phố."},
            "Phụ bếp": {"min": 500, "max": 1200, "cd": 4, "desc": "Làm việc tại nhà bếp "},
            "Thám hiểm": {"min": 1000, "max": 1500, "cd": 12, "desc": "Đi Thám Hiểm Khu Vực Mới"},
            "Phụ Hồ": {"min": 2000, "max": 4000, "cd": 24, "desc": "Làm Phụ Hồ Ở Công Trường."}
        }
        
    @commands.command()
    async def work(self, ctx):
        try:
            data = await self.bot.db.get_user_full(ctx.author.id)
            active = data[1]

            embed = discord.Embed(
                title="💼 Thăm ngàn Hub",
                description="Chọn việc bên dưới:",
                color=discord.Color.blue()
            )

            # Phải truyền ctx.author vào đây để JobView nhận được
            view = JobView(self.jobs, self.bot, active, ctx.author) 

            await ctx.send(embed=embed, view=view)

        except Exception as e:
            print(f"❌ LỖI TẠI LỆNH WORK: {e}")
            await ctx.send(f"Có lỗi xảy ra: {e}")

    @commands.command()
    async def flip(self, ctx, choice: str, bet: int):
        # 1. Chuẩn hóa lựa chọn của người chơi
        choice = choice.lower()
        if choice not in ['head', 'tail']:
            return await ctx.send("❌ Bạn chỉ được chọn `head` (sấp) hoặc `tail` (ngửa)!")

        # 2. Lấy dữ liệu user (Dùng 3 biến để khớp với database đã nâng cấp)
        # Sửa lỗi "expected 2, got 3" bằng cách thêm dấu , _
        money, active, _ = await self.bot.db.get_user(ctx.author.id)
        
        if bet <= 0:
            return await ctx.send("❌ Số tiền cược phải lớn hơn 0!")
        if bet > money:
            return await ctx.send(f"❌ Bạn không đủ tiền! Số dư hiện tại: **{money:,} xu**")

        # 3. Tỉ lệ thắng (Mặc định 50%, Rodion buff lên 60%)
        win_rate = 50
        skill_text = ""
        if active == "Rodion":
            win_rate = 60
            skill_text = "🎲 **Rodion:** 'Ván này chắc chắn thắng...' (Tỉ lệ thắng +10%)"

        # 4. Tung xu ngẫu nhiên
        result = "head" if random.randint(1, 100) <= win_rate else "tail"
        
        
        # Tạo Embed hiển thị trạng thái đang chờ
        waiting_embed = discord.Embed(
            title="<a:coin1:1496027671178772673> Đang Tung Xu...", # Tiêu đề sạch
            description=f"{skill_text}\nBạn chọn: **{choice.upper()}** | Cược: **{bet:,} xu**",
            color=discord.Color.gold()
        )
        msg = await ctx.send(embed=waiting_embed)
         
        # Hiệu ứng chờ 2 giây cho kịch tính
        await asyncio.sleep(2) 

        # 5. Kiểm tra thắng thua và cập nhật tiền vào DB
        is_win = (choice == result)
        if is_win:
            await self.bot.db.update_money(ctx.author.id, bet)
            color = discord.Color.green()
            title = "🎉 Bạn Đã Thắng!"
            desc = f"Kết quả là: **{result.upper()}**\nBạn nhận được **+{bet:,} xu**."
        else:
            await self.bot.db.update_money(ctx.author.id, -bet)
            color = discord.Color.red()
            title = "💀 Oánh Ngu Như Lợn "
            desc = f"Kết quả là: **{result.upper()}**\nBạn đã mất **-{bet:,} xu**."

        # Cập nhật Embed kết quả cuối cùng
        final_embed = discord.Embed(title=title, description=desc, color=color)
        final_embed.set_footer(text=f"Người chơi: {ctx.author.name}")
        
        # Ảnh minh họa mặt xu (Bạn có thể đổi link ảnh của mình vào đây)
        if result == "head":
            final_embed.set_thumbnail(url="https://i.imgur.com/39A8n8M.png")
        else:
            final_embed.set_thumbnail(url="https://i.imgur.com/L1S0F0p.png")

        await msg.edit(embed=final_embed)

async def setup(bot):
    await bot.add_cog(Economy(bot))
