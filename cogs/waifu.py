import discord
import traceback
import sys
from discord.ext import commands

class WaifuProfileView(discord.ui.View):
    def __init__(self, bot, user_id, waifus, waifu_info):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        
        options = [
            discord.SelectOption(
                label=f"{w['waifu_name']} (Lv {w['level']})", 
                value=w['waifu_name'],
                emoji="🌸"
            ) for w in waifus
        ]
        
        # Ban đầu View chỉ có mỗi Select Menu
        self.add_item(WaifuSelect(options, self.bot, waifu_info))

class WaifuSelect(discord.ui.Select):
    def __init__(self, options, bot, waifu_info):
        self.bot = bot
        self.waifu_info = waifu_info
        super().__init__(placeholder="Chọn Waifu để xem hồ sơ...", options=options)

    async def callback(self, interaction: discord.Interaction):
        waifu_name = self.values[0]
        user_id = interaction.user.id
        
        # 1. Lấy dữ liệu từ Database
        data = await self.bot.db.get_waifu_data(user_id, waifu_name)
        level = data['level']
        exp = data['exp']
        
        # 2. Lấy thông tin chi tiết
        details = self.waifu_info.get(waifu_name, {"desc": "Chưa có mô tả.", "image": ""})
        
        # 3. Tạo Embed mới
        embed = discord.Embed(
            title=f"Thông tin — {waifu_name} ⭐",
            description=details["desc"],
            color=0xffc0cb
        )
        if details["image"]:
            embed.set_image(url=details["image"])
            
        # Tính thanh EXP mốc 1250, 4500, 10000
        exp_map = {1: 1250, 2: 4500, 3: 10000}
        max_exp = exp_map.get(level, 10000)
        percent = min(int((exp / max_exp) * 10), 10)
        bar = "█" * percent + "░" * (10 - percent)
        embed.add_field(name=f"🎖️ Cấp độ: {level}", value=f"{bar} ({exp}/{max_exp})", inline=False)

        # 4. LOGIC HIỆN NÚT: Khi đã chọn waifu, ta tạo một View mới có chứa NÚT
        # Chúng ta sẽ cập nhật lại View hiện tại
        view = self.view
        
        # Xóa tất cả item hiện có (bao gồm cả cái Select này) để sắp xếp lại
        view.clear_items()
        
        # Thêm lại chính cái Select này (để người dùng có thể chọn con khác)
        view.add_item(self)
        
        # THÊM NÚT "ĐẶT LÀM ĐẠI DIỆN" (Nút này giờ mới xuất hiện)
        # Chúng ta tạo nút trực tiếp ở đây
        btn_active = discord.ui.Button(label="Đặt làm Waifu đại diện", style=discord.ButtonStyle.success, emoji="💖")
        
        # Định nghĩa hành động khi bấm nút
        async def btn_callback(it: discord.Interaction):
            await self.bot.db.set_active_waifu(it.user.id, waifu_name)
            await it.response.send_message(f"✅ Đã đặt **{waifu_name}** làm người đồng hành!", ephemeral=True)
            
        btn_active.callback = btn_callback
        view.add_item(btn_active)

        # Cập nhật tin nhắn với Embed và View mới (đã có thêm nút)
        await interaction.response.edit_message(embed=embed, view=view)
    

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
                embed.add_field(name=f"{name} — {info['price']:,} xu", inline=False)
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
                "Don Quixote": {"price": 2000, "base_buff": 5, "unit": "%", "type": "work_money"},
                "Mahiru": {"price": 3000, "base_buff": 20, "unit": "%", "type": "work_money"},
                "Ganyu": {"price": 8000, "base_buff": 5, "unit": " phút", "type": "work_cd"}
            },
            "Gambling 🎲": {
                "Rodion": {"price": 5000, "base_buff": 10, "unit": "%", "type": "gamble_luck"},
                "Yumeko": {"price": 12000, "base_buff": 7, "unit": "%", "type": "global_luck"}
            },
            "Special Buff ✨": {
                "Faust": {"price": 15000, "base_buff": 20, "unit": "%", "type": "work_cd",
                "Makima": {"price": 25000, "base_buff": 50, "unit": "%", "type": "penalty_reduction"}
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

        self.waifu_info = {
            "Mahiru": {
                "desc": """Mahiru vô tội, dễ thương, tốt bụng và giàu tình yêu thương, với một la bàn đạo đức vững vàng và lòng hào phóng sâu sắc. Cô ấy rất dịu dàng và vị tha, luôn cố gắng giúp đỡ người khác khi cảm thấy an toàn để làm vậy.\n
                Dù giữ thái độ dè dặt, đặc biệt khi nói về cha mẹ, cô tránh nói dối và thường trở nên kín đáo, hơi xa cách khi nhắc đến những tổn thương trong quá khứ.
                Sự chân thành riêng tư của cô bộc lộ rõ hơn khi ở một mình, nhưng cô không bao giờ thể hiện điều đó một cách gay gắt.""",
                "image": "https://media.tenor.com/rLKqg7FmVYwAAAAd/angel-tenshi.gif" # Thay link ảnh thật của An vào
            },
            "Don Quixote": {
                "desc": "h",
                "image": "https://i.imgur.com/8nS8z4p.png"
            },
            "Ganyu": {
                "desc": "Thư ký tận tụy của Nguyệt Hải Đình.",
                "image": "https://i.imgur.com/8nS8z4p.png"
            }
        }

    def get_waifu_info(self, name):
        """Hàm phụ trợ để tìm dữ liệu waifu nhanh từ dict categories"""
        for cat in self.categories.values():
            if name in cat:
                return cat[name]
        return None

    def calculate_bonus(self, waifu_name, level, effect_type):
        """
        Hàm tính toán buff tổng quát.
        Sử dụng: calculate_bonus("Mahiru", 2, "work_money") -> Trả về 1.2x (ví dụ)
        """
        info = self.get_waifu_info(waifu_name)
        if not info or info['type'] != effect_type:
            return 1.0 if "money" in effect_type or "luck" in effect_type else 1.0 # Default multipliers

        # Công thức: base + (mỗi level tăng thêm 10% của chỉ số gốc)
        growth = 1 + (level - 1) * 0.1
        actual_buff = info['base_buff'] * growth

        if effect_type == "work_money":
            return 1 + (actual_buff / 100)
        elif effect_type == "work_cd":
            # Nếu là Ganyu (đơn vị phút), ta trả về số phút giảm. 
            # Nếu là Faust (đơn vị %), ta trả về tỉ lệ giảm.
            return actual_buff 
        elif effect_type == "gamble_luck":
            return actual_buff # Trả về số % cộng thêm vào tỉ lệ thắng
            
        return 1.0
    

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

    @commands.command(name="item")
    async def item(self, ctx, item_id: str = None, *, waifu_name: str = None):
        if not item_id or not waifu_name:
            return await ctx.send("⚠️ Cách dùng: `!item [ID_Vật_Phẩm] [Tên_Waifu]`\nVí dụ: `!item Stone Mahiru`")

        user_id = ctx.author.id
        
        # 1. Kiểm tra vật phẩm trong kho (user_items)
        async with aiosqlite.connect(self.bot.db.db_path) as db:
            async with db.execute(
                "SELECT quantity FROM user_items WHERE user_id = ? AND item_name = ?", 
                (user_id, item_id)
            ) as cursor:
                row = await cursor.fetchone()
                if not row or row[0] <= 0:
                    return await ctx.send(f"❌ Bạn không có `{item_id}` trong kho đồ!")

        # 2. Tìm Waifu trong inventory (hỗ trợ tìm tên gần đúng)
        inventory = await self.bot.db.get_all_waifus(user_id)
        target_waifu = next((w['waifu_name'] for w in inventory if waifu_name.lower() in w['waifu_name'].lower()), None)
        
        if not target_waifu:
            return await ctx.send(f"❌ Bạn không sở hữu Waifu nào tên `{waifu_name}`!")

        # 3. Cấu hình lượng EXP cho từng loại đá/sách
        exp_values = {
            "ExpBook": 100,
            "Gift": 250,
            "Stone": 500  # <--- Stone của An ở đây
        }
        
        gain = exp_values.get(item_id)
        if gain is None:
            return await ctx.send(f"❌ Vật phẩm `{item_id}` không thể dùng để tăng cấp!")

        # 4. Thực hiện trừ item và cộng EXP vào DB
        await self.bot.db.update_item_quantity(user_id, item_id, -1)
        result = await self.bot.db.update_waifu_exp(user_id, target_waifu, gain)

        if result:
            lv, xp = result
            # Hiển thị kết quả
            embed = discord.Embed(
                title="✨ Sử dụng vật phẩm thành công!",
                description=f"Đã dùng **{item_id}** (+{gain} EXP) cho **{target_waifu}**",
                color=discord.Color.green()
            )
            status = f"Level: **{lv}**" + (f" | EXP: **{xp}**" if lv < 4 else " (MAX)")
            embed.add_field(name="Trạng thái mới", value=status)
            await ctx.send(embed=embed)
        
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
            exp_map = {1: 1250, 2: 4000, 3: 10000}
            
            # Lấy mốc exp cần thiết dựa trên level hiện tại, nếu max level (4) thì lấy mốc lv 3
            current_max_exp = exp_map.get(level, 10000)
            
            # Tính phần trăm (giới hạn tối đa 100% để thanh bar không bị tràn)
            percent = min(int((exp / current_max_exp) * 10), 10)
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
        waifus = await self.bot.db.get_all_waifus(user_id)

        if not waifus:
            return await ctx.send("❌ Bạn chưa sở hữu Waifu nào!")

        # Embed ban đầu: Rất đơn giản, không có ảnh
        embed = discord.Embed(
            title="🌸 Danh Sách Waifu", 
            description="Vui lòng chọn một Waifu từ danh sách dưới đây để xem chi tiết.", 
            color=0xffc0cb
        )
        
        # View ban đầu: Chỉ có Menu thả xuống, chưa có nút bấm
        view = WaifuProfileView(self.bot, user_id, waifus, self.waifu_info)
        await ctx.send(embed=embed, view=view)
        
async def setup(bot):
    await bot.add_cog(Waifu(bot))
