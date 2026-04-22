import discord
import traceback
import sys
from discord.ext import commands

class WaifuProfileView(discord.ui.View):
    def __init__(self, bot, user_id, waifus):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        
        options = [
            discord.SelectOption(
                label=f"{w['waifu_name']} (Lv {w['level']})", 
                value=w['waifu_name']
            ) for w in waifus
        ]
        # ✅ FIX quan trọng: Truyền cả bot vào WaifuSelect
        self.add_item(WaifuSelect(options, self.bot))

    @discord.ui.button(label="Đặt làm waifu đại diện", style=discord.ButtonStyle.primary)
    async def set_active(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Kiểm tra nếu chưa chọn waifu từ menu
        if not interaction.message.embeds or " — " not in interaction.message.embeds[0].title:
            return await interaction.response.send_message("❌ Vui lòng chọn một Waifu từ danh sách trước!", ephemeral=True)
            
        title = interaction.message.embeds[0].title
        waifu_name = title.split(" — ")[1].replace(" ⭐", "")
        
        # ✅ Dùng self.bot.db để lưu
        await self.bot.db.set_active_waifu(interaction.user.id, waifu_name)
        await interaction.response.send_message(f"✅ Đã đặt **{waifu_name}** làm Waifu đại diện!", ephemeral=True)

    @discord.ui.button(label="Xem kĩ năng", style=discord.ButtonStyle.secondary)
    async def view_skills(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.message.embeds or " — " not in interaction.message.embeds[0].title:
            return await interaction.response.send_message("❌ Vui lòng chọn một Waifu để xem kỹ năng!", ephemeral=True)

        title = interaction.message.embeds[0].title
        waifu_name = title.split(" — ")[1].replace(" ⭐", "")
        
        # ✅ Lấy level từ database thông qua self.bot
        _, _, _, level, _ = await self.bot.db.get_user_full(interaction.user.id)
        
        waifu_cog = self.bot.get_cog("Waifu")
        target_info = None
        for cat in waifu_cog.categories.values():
            if waifu_name in cat:
                target_info = cat[waifu_name]
                break

        if not target_info:
            return await interaction.response.send_message("❌ Không tìm thấy thông tin kỹ năng!", ephemeral=True)

        final_power = target_info['base_buff'] * (1 + (level - 1) * 0.2)
        
        embed = discord.Embed(title=f"⚔️ Kỹ năng: {waifu_name}", color=0x3498db)
        embed.add_field(name="Hiệu quả hiện tại", value=f"**+{final_power:.1f}{target_info['unit']}**", inline=True)
        embed.add_field(name="Cấp độ nhân vật", value=f"Lv.{level}", inline=True)
        embed.add_field(name="Mô tả", value=target_info['desc'], inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class WaifuSelect(discord.ui.Select):
    def __init__(self, options, bot):
        super().__init__(placeholder="Chọn waifu để xem chi tiết", options=options)
        self.bot = bot # Lưu bot để gọi database

    async def callback(self, interaction: discord.Interaction):
        waifu_name = self.values[0]
        
        # Lấy data từ DB (Level và EXP)
        waifu_data = await self.bot.db.get_waifu_data(interaction.user.id, waifu_name)
        level = waifu_data['level'] if waifu_data else 1
        exp = waifu_data['exp'] if waifu_data else 0
        
        # Tạo thanh EXP
        max_exp = level * 100
        percent = min(int((exp / max_exp) * 10), 10) if level < 4 else 10
        exp_bar = "█" * percent + "░" * (10 - percent)
        exp_text = f"{exp}/{max_exp} EXP" if level < 4 else "Đạt cấp tối đa"

        embed = discord.Embed(title=f"💕 Waifu — {waifu_name} ⭐", color=0xff99ff)
        
        # Lấy ảnh từ Cog Waifu
        waifu_cog = self.bot.get_cog("Waifu")
        # Khai báo waifu_images trong class Waifu (bên dưới) để dòng này không lỗi
        images = {
            "Mahiru": "https://i.imgur.com/8nS8z4p.png", # Ví dụ ảnh
            "Castorice": "https://i.imgur.com/8nS8z4p.png"
        }
        img_url = images.get(waifu_name, "https://i.imgur.com/8nS8z4p.png")
        embed.set_thumbnail(url=img_url)
        
        embed.add_field(name="💖 Kinh nghiệm (EXP)", value=f"`{exp_bar}`\n{exp_text}", inline=True)
        embed.add_field(name="🎖️ Cấp độ", value=f"Level {level}", inline=True)

        # Quan trọng: Chỉ dùng edit_message
        await interaction.response.edit_message(embed=embed)
    

class ShopDropdown(discord.ui.Select):
    def __init__(self, categories):
        self.categories = categories
        options = [
            discord.SelectOption(label=cat, description=f"Xem các Waifu hệ {cat}") 
            for cat in categories.keys()
        ]
        super().__init__(placeholder="Chọn danh mục buff...", options=options)

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        items = self.categories[category]
        
        embed = discord.Embed(title=f"🛒 Shop: {category}", color=discord.Color.gold())
        for name, info in items.items():
            embed.add_field(
                name=f"{name} — {info['price']} xu", 
                value=f"*{info['desc']}*", 
                inline=False
            )
        
        await interaction.response.edit_message(embed=embed)

class ShopView(discord.ui.View):
    def __init__(self, categories, items_data, author, bot):
        super().__init__(timeout=60)
        self.categories = categories
        self.items_data = items_data
        self.author = author
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ Menu này không dành cho bạn!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Shop Waifu 🎭", style=discord.ButtonStyle.primary)
    async def waifu_shop(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🛒 Cửa hàng Waifu", color=discord.Color.pink())
        for cat, content in self.categories.items():
            for name, info in content.items():
                embed.add_field(name=f"{name} — {info['price']:,} xu", value=info['desc'], inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Shop Vật phẩm 🎁", style=discord.ButtonStyle.success)
    async def item_shop(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="📦 Cửa hàng Vật phẩm", color=discord.Color.blue())
        for name, info in self.items_data.items():
            embed.add_field(name=f"{name} — {info['price']:,} xu", value=info['desc'], inline=False)
        await interaction.response.edit_message(embed=embed, view=self)
        
class Waifu(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Giá và thông tin waifu
        
        self.categories = {
            "Economy 💰": {
                "Don Quixote": {"price": 2000, "base_buff": 15, "unit": "%", "desc": "Tăng tiền khi làm việc"},
                "Mahiru": {"price": 3000, "base_buff": 20, "unit": "%", "desc": "Tăng lương mỗi ngày"},
                "Ganyu": {"price": 8000, "base_buff": 5, "unit": " phút", "desc": "Giảm hồi chiêu làm việc"}
            },
            "Gambling 🎲": {
                "Rodion": {"price": 5000, "base_buff": 10, "unit": "%", "desc": "Tăng tỉ lệ thắng cược"},
                "Yumeko": {"price": 12000, "base_buff": 7, "unit": "%", "desc": "Tăng tỉ lệ thắng tất cả game"}
            },
            "Special Buff ✨": {
                "Faust": {"price": 15000, "base_buff": 20, "unit": "%", "desc": "Giảm thời gian chờ lệnh"},
                "Makima": {"price": 25000, "base_buff": 50, "unit": "%", "desc": "Giảm tiền phạt khi thất bại"}
            }
        }
        
        self.item_data = {
            "Sách Kinh Nghiệm": {
                "price": 500, 
                "desc": "Tăng 100 EXP cho Waifu đang chọn.`id: ExpBook`",
                "exp_gain": 100
            },
            "Quà Tặng Cao Cấp": {
                "price": 2000, 
                "desc": "Tăng 500 EXP cho Waifu đang chọn. `id: Gift`",
                "exp_gain": 500
            },
            "Đá Cường Hóa": {
                "price": 5000, 
                "desc": "Vật phẩm quý hiếm dùng để nâng cấp bậc Skill `id: stone`.",
                "exp_gain": 0
            }
        }
        
        self.active_responses = {
        # Nhóm Economy
        "Don Quixote": "'To reach the unreachable star! 🌟'",
        "Mahiru": "🧺 'Để em lo liệu việc chi tiêu và chuẩn bị mọi thứ cho anh thật chu đáo nhé.'",
        "Ganyu": "📑 'Lượng công việc này vẫn trong tầm kiểm soát. Tôi sẽ hoàn thành chúng sớm hơn dự kiến.'",
        
        # Nhóm Gambling
        "Rodion": "'If she could forget everything, and begin afresh. 🎲'",
        "Yumeko": "🎴 'Cùng nhau rơi vào vòng xoáy của sự hưng phấn này nào! Đặt cược thôi!'",
        
        # Nhóm Special Buff
        "Faust": "'Man errs, as long as he strives. 📖'",
        "Makima": "🐕 'Mọi thứ đều đang nằm trong tầm kiểm soát. Đừng lo lắng về những thất bại nhỏ nhặt.'"
    }
        

    @commands.command()
    async def shop(self, ctx):
        embed = discord.Embed(
            title="🎭 Trung Tâm Tuyển Dụng Waifu",
            description="Hãy chọn loại kỹ năng bạn muốn hỗ trợ từ menu bên dưới.",
            color=discord.Color.blue()
        )
        view = ShopView(self.categories, self.item_data, ctx.author, self.bot)
        await ctx.send(embed=embed, view=view)

    @commands.command(name="buywaifu")
    async def buywaifu(self, ctx, *, name: str):
        target_info = None
        target_name = None
        
        # Tìm kiếm waifu trong tất cả danh mục
        for cat, items in self.categories.items():
            for k, v in items.items():
                if name.lower() in k.lower():
                    target_name = k
                    target_info = v
                    break
        
        if not target_name: 
            return await ctx.send("❌ Không tìm thấy Waifu này!")

        # Kiểm tra túi đồ
        inv = await self.bot.db.get_inventory(ctx.author.id)
        if target_name in inv:
            return await ctx.send("❌ Bạn đã sở hữu cô nàng này rồi!")

        price = target_info['price']
        money, _, _ = await self.bot.db.get_user(ctx.author.id)
        
        if money < price: 
            return await ctx.send(f"❌ Bạn còn thiếu {price - money} xu!")
        
        # Trừ tiền và thêm vào kho
        await self.bot.db.update_money(ctx.author.id, -price)
        await self.bot.db.add_waifu(ctx.author.id, target_name)
        
        await ctx.send(f"🎉 Chúc mừng! Bạn đã rước **{target_name}** về đội với giá **{price} xu**!")
        
    @commands.command(aliases=['i', 'inv'])
    async def inventory(self, ctx):
        """Xem số dư xu và các vật phẩm sở hữu"""
        user_id = ctx.author.id
        
        # 1. Lấy dữ liệu từ database
        # Giả sử hàm get_inventory trả về tất cả items (bao gồm cả waifu)
        all_items = await self.bot.db.get_inventory(user_id) 
        money, active, _ = await self.bot.db.get_user(user_id)

        embed = discord.Embed(
            title=f"🎒 Kho đồ của {ctx.author.name}", 
            color=discord.Color.blue()
        )
        
        # --- Hiển thị Coin ---
        embed.add_field(name="💰 Tài sản", value=f"**{money:,}** xu", inline=False)
        
        # --- Hiển thị Items (Lọc bỏ các Waifu) ---
        # Danh sách tên các Waifu để bot biết đường mà né không hiện vào inv
        waifu_names = ["Don Quixote", "Mahiru", "Ganyu", "Rodion", "Yumeko", "Faust", "Makima"]
        
        # Chỉ lấy những gì KHÔNG nằm trong danh sách Waifu
        items_only = [item for item in all_items if item not in waifu_names]
        
        if not items_only:
            item_list = "*Không có vật phẩm nào*"
        else:
            # Ví dụ: • Sách Kinh Nghiệm
            item_list = "\n".join([f"• {it}" for it in items_only])
            
        embed.add_field(name="📦 Vật phẩm sở hữu", value=item_list, inline=False)
        
        embed.set_footer(text="Dùng !waifu để xem danh sách Waifu của bạn!")
        await ctx.send(embed=embed)

    @commands.command()
    async def usewaifu(self, ctx, *, name: str):
        user_id = ctx.author.id
        inv = await self.bot.db.get_inventory(user_id)

        # Tìm waifu trong túi đồ
        target = None
        for waifu in inv:
            if name.lower() in waifu.lower():
                target = waifu
                break

        if not target:
            return await ctx.send("❌ Bạn không sở hữu waifu này!")

        # Cập nhật database
        await self.bot.db.set_active_waifu(user_id, target)

        # Lấy câu thoại từ từ điển (nếu không có thì dùng câu mặc định)
        response = self.active_responses.get(target, "Đã chọn làm bạn đồng hành!")

        embed = discord.Embed(
            title="✨ Kích Hoạt Kỹ Năng",
            description=f"Bạn đã chọn **{target}** làm trợ thủ đắc lực!",
            color=discord.Color.green()
        )
        # Thêm câu thoại vào Embed
        embed.add_field(name="description:", value=f"*{response}*", inline=False)
        await ctx.send(embed=embed)
        
    @commands.command(name="buyitem")
    async def buyitem(self, ctx, item_name: str = None, amount: int = 1):
        if not item_name:
            return await ctx.send("⚠️ Cách dùng: `!buyitem [id_vật_phẩm] [số_lượng]`\nVí dụ: `!buyitem ExpBook 5`")
        
        if amount <= 0:
            return await ctx.send("❌ Số lượng phải lớn hơn 0!")

        # Định nghĩa các món hàng trong Shop
        shop_items = {
            "ExpBook": {"price": 500, "desc": "Tăng 50 EXP cho Waifu ,`id: expBook`"},
            "Gift": {"price": 1000, "desc": "Tăng độ thân thiết , `id: Gift`"},
            "Stone": {"price": 5000, "desc": "Reset lại chỉ số kỹ năng, `id: stone`"}
        }

        # Kiểm tra item có tồn tại không
        if item_name not in shop_items:
            list_items = ", ".join([f"`{name}`" for name in shop_items.keys()])
            return await ctx.send(f"❌ Vật phẩm không tồn tại! Shop đang bán: {list_items}")

        item_data = shop_items[item_name]
        total_price = item_data['price'] * amount
        user_money = await self.bot.db.get_money(ctx.author.id)

        # Kiểm tra đủ tiền không
        if user_money < total_price:
            return await ctx.send(f"❌ Bạn không đủ tiền! Cần **{total_price:,} 💰** nhưng bạn chỉ có **{user_money:,} 💰**")

        # Thực hiện giao dịch
        await self.bot.db.buy_item_db(ctx.author.id, item_name, item_data['price'], amount)
        
        embed = discord.Embed(
            title="🛒 Giao dịch thành công", 
            description=f"Bạn đã mua thành công **{amount}x {item_name}**",
            color=discord.Color.green()
        )
        embed.add_field(name="Tổng chi phí", value=f"{total_price:,} 💰")
        embed.add_field(name="Số dư còn lại", value=f"{user_money - total_price:,} 💰")
        embed.set_footer(text="Dùng !inventory để xem kho đồ của bạn")
        
        await ctx.send(embed=embed)

    @commands.command()
    async def useitem(self, ctx, *, item_name: str):
        # Kiểm tra số lượng item trong DB (An tự viết thêm hàm get_item_count nhé)
        # Nếu có item:
        await self.bot.db.update_item_quantity(ctx.author.id, item_name, -1)
        new_lv, new_exp = await self.bot.db.update_waifu_exp(ctx.author.id, 100) # Cộng 100 exp
        await ctx.send(f"✨ Bạn đã dùng **{item_name}**! Waifu hiện tại đạt Level {new_lv} ({new_exp} EXP).")
        
    @commands.command(aliases=['p'])
    async def profile(self, ctx):
        user_id = ctx.author.id
        # Lấy thông tin đầy đủ (money, active_waifu, last_work, level, exp)
        money, active, _, level, exp = await self.bot.db.get_user_full(user_id)

        embed = discord.Embed(title=f"👤 Hồ sơ của {ctx.author.name}", color=discord.Color.blue())
        embed.set_thumbnail(url=ctx.author.avatar.url)
        
        embed.add_field(name="💰 Tài sản", value=f"{money:,} xu", inline=True)
        
        # Kiểm tra xem có Waifu đại diện không
        if active:
            # An có thể tạo thêm một dict chứa ảnh profile của từng Waifu
            waifu_images = {
                "Castorice": "URL_ẢNH_GIF_LUNG_LINH",
                "Mahiru": "URL_ẢNH_MAHIRU"
            }
            img_url = waifu_images.get(active, "")
            if img_url: embed.set_image(url=img_url)

            # Thanh EXP cho Waifu đại diện
            max_exp = level * 100
            percent = int((exp / max_exp) * 10)
            bar = "█" * percent + "░" * (10 - percent)
            
            embed.add_field(name="❤️ Waifu đại diện", value=f"**{active}**", inline=True)
            embed.add_field(name=f"🎖️ Cấp độ: {level}", value=f"{bar} ({exp}/{max_exp})", inline=False)
        else:
            embed.add_field(name="❤️ Waifu đại diện", value="Chưa thiết lập", inline=True)
            embed.set_footer(text="Dùng !waifu để chọn người đồng hành!")

        await ctx.send(embed=embed)
        
    @commands.command()
    async def waifu(self, ctx):
        user_id = ctx.author.id
        waifus = await self.bot.db.get_all_waifus(user_id) # Lấy data từ DB

        if not waifus:
            return await ctx.send("❌ Bạn chưa sở hữu Waifu nào!")

        embed = discord.Embed(
            title="🎴 Danh sách waifu",
            description="Chọn waifu để xem thông tin chi tiết.",
            color=discord.Color.dark_grey()
        )
        
        view = WaifuProfileView(self.bot, user_id, waifus)
        await ctx.send(embed=embed, view=view)
        
async def setup(bot):
    await bot.add_cog(Waifu(bot))
