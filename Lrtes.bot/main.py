import os
import random
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from flask import Flask
from threading import Thread
from google import genai

# --- ԿԱՐԳԱՎՈՐՈՒՄՆԵՐ ---
TOKEN = "YOUR_BOT_TOKEN_HERE"          # Փոխարինեք ձեր Telegram բոտի թոքենով
ADMIN_ID = 123456789                  # Գրեք ձեր Telegram ID-ն (որպես ադմին)
GEMINI_API_KEY = "YOUR_GEMINI_KEY_HERE" # Ձեր Gemini API ստեղնը (Key)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Gemini գլայենդի կարգավորում
client = genai.Client(api_key=GEMINI_API_KEY)

logging.basicConfig(level=logging.INFO)

# Flask սերվեր (Render/Koyeb/GitHub հոսթինգների համար, որ 24/7 աշխատի)
app = Flask('')

@app.route('/')
def home():
    return "I am alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Խաղի թեմաներ և ադմինական կարգավորումներ
THEMES = {
    "normal": {"spy": "լրտես", "name": "Ստանդարտ"},
    "new_year": {"spy": "ձմեր պապիկ", "name": "Ամանորյա 🎄"},
    "halloween": {"spy": "զոմբի", "name": "Հելոինի 🎃"},
    "valentin": {"spy": "վալենտին", "name": "Սիրահարների տոնի ❤️"}
}
current_theme = "normal"

# Հիշողության տվյալների բազա
users_points = {}       # {user_id: points}
banned_users = set()    # Արգելափակված օգտատերեր
active_games = {}       # {chat_id: game_data}

# FSM վիճակներ (States)
class States(StatesGroup):
    waiting_for_donation_amount = State()
    waiting_for_anonymous_msg = State()
    waiting_for_admin_broadcast = State()

# --- ԳԼԽԱՎՈՐ ՄԵՆՅՈՒԻ ԿՈՃԱԿՆԵՐ ---
def get_main_menu_keyboard(bot_username: str):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Դոնատ ադմինին", callback_data="donate_admin")],
        [InlineKeyboardButton(text="✉️ Անանուն նամակ ադմինին", callback_data="anon_msg")],
        [InlineKeyboardButton(text="➕ Ավելացնել չատը սեփական բոտում", url=f"https://t.me/{bot_username}?startgroup=true")]
    ])
    return keyboard

# --- /start ՀՐԱՄԱՆ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if str(message.from_user.id) in banned_users or message.from_user.username in banned_users:
        return await message.reply("Դուք արգելափակված եք այս բոտում:")
    
    bot_info = await bot.get_me()
    welcome_text = (
        "🤖 **Ես բոտ խաղավարն եմ և այլն!**\n\n"
        "Բարի գալուստ «Լրտես» խաղ: Այս բոտի միջոցով դուք կարող եք խաղալ ձեր ընկերների հետ, ուղարկել անանուն նամակներ, աստղեր նվիրել ադմինին և այլն:\n\n"
        "📌 **Հիմնական հրամանները՝**\n"
        "/game_hay_lrtes - Սկսել նոր խաղային գրանցում\n"
        "/top_hay_lrtes - Տեսնել թոփ 10 մասնակիցներին\n"
        "/cancel_game - Չեղարկել ընթացիկ խաղը"
    )
    await message.answer(welcome_text, reply_markup=get_main_menu_keyboard(bot_info.username), parse_mode="Markdown")


# --- ԴՈՆԱՏ ԵՎ ԱՆԱՆՈՒՆ ՆԱՄԱԿՆԵՐ ---
@dp.callback_query(F.data == "donate_admin")
async def cb_donate(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("⭐ Գրեք, թե քանի աստղ եք ցանկանում դոնատ անել ադմինին (գրեք միայն թիվ):")
    await state.set_state(States.waiting_for_donation_amount)
    await callback.answer()

@dp.message(States.waiting_for_donation_amount)
async def process_donation(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text)
        await bot.send_message(ADMIN_ID, f"⭐ **Նոր դոնատ!**\nՕգտատեր՝ {message.from_user.full_name} (@{message.from_user.username})\nՑանկանում է նվիրել: **{amount} աստղ**:")
        await message.reply(f"Շնորհակալություն! {amount} աստղի դոնատի հարցումը ուղարկվեց ադմինին:")
    except ValueError:
        await message.reply("Խնդրում եմ գրել միայն թիվ:")
    await state.clear()

@dp.callback_query(F.data == "anon_msg")
async def cb_anon(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("✉️ Գրեք ձեր անանուն նամակը ադմինին, և այն անմիջապես կփոխանցվի:")
    await state.set_state(States.waiting_for_anonymous_msg)
    await callback.answer()

@dp.message(States.waiting_for_anonymous_msg)
async def process_anon_msg(message: types.Message, state: FSMContext):
    user = message.from_user
    text = (
        f"✉️ **Անանուն նամակ:**\n\n"
        f"{message.text}\n\n"
        f"👤 Նիկնեյմ: {user.full_name} (@{user.username if user.username else 'չկա'})\n"
        f"🆔 Ուսեր Այդի: `{user.id}`"
    )
    await bot.send_message(ADMIN_ID, text, parse_mode="Markdown")
    await message.reply("✅ Ձեր անանուն նամակը հաջողությամբ հասավ ադմինին:")
    await state.clear()


# --- ԼՐՏԵՍ ԽԱՂԻ ՀԱՄԱԿԱՐԳ ---

@dp.message(Command("game_hay_lrtes"))
async def cmd_game_start_reg(message: types.Message):
    chat_id = message.chat.id
    if chat_id in active_games:
        return await message.reply("⚠️ Այս չատում արդեն կա ակտիվ խաղ կամ գրանցում:")
    
    active_games[chat_id] = {
        "status": "registration",
        "players": {}, # {user_id: full_name}
        "paid_players": set(),
        "creator": message.from_user.id
    }
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Միանալ խաղին", callback_data="join_game")]
    ])
    await message.answer(
        "🕵️‍♂️️ **Արի լրտեսը քեզ է սպասում!**\n\n"
        "• Մինիմում մասնակիցներ՝ 3\n"
        "• Մաքսիմում մասնակիցներ՝ 20\n"
        "• Առաջին 12 մասնակիցն մասնակցում է անվճար, մնացած 8-ը՝ 5 աստղով։\n\n"
        "**Միացածների ցանկ՝**\n(դեռևս ոչ ոք չի միացել)",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "join_game")
async def cb_join_game(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    user = callback.from_user
    
    if chat_id not in active_games or active_games[chat_id]["status"] != "registration":
        return await callback.answer("Խաղի գրանցումն ավարտված է կամ չկա ակտիվ խաղ:", show_alert=True)
    
    game = active_games[chat_id]
    if user.id in game["players"]:
        return await callback.answer("Դուք արդեն միացել եք խաղին!", show_alert=True)
    
    if len(game["players"]) >= 20:
        return await callback.answer("Խաղն արդեն լցվել է (առավելագույնը 20 հոգի):", show_alert=True)
    
    # 12-րդ մասնակցից հետո պահանջվում է 5 աստղ
    if len(game["players"]) >= 12:
        if user.id not in game["paid_players"]:
            game["paid_players"].add(user.id) # Պայմանականորեն գրանցում ենք վճարված
    
    game["players"][user.id] = user.full_name
    
    players_list_str = "\n".join([f"• {name}" for name in game["players"].values()])
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Միանալ խաղին", callback_data="join_game")]
    ])
    
    try:
        await callback.message.edit_text(
            "🕵️‍♂️ **Արի լրտեսը քեզ է սպասում!**\n\n"
            f"Մասնակիցների քանակը: {len(game['players'])}/20\n\n"
            f"**Միացածներ՝**\n{players_list_str}",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    except Exception:
        pass
    await callback.answer("Դուք հաջողությամբ միացաք խաղին!")

@dp.message(Command("start_hay_lrtes"))
async def cmd_run_game(message: types.Message):
    chat_id = message.chat.id
    if chat_id not in active_games or active_games[chat_id]["status"] != "registration":
        return await message.reply("Գրանցման փուլում գտնվող ակտիվ խաղ չկա:")
    
    game = active_games[chat_id]
    if len(game["players"]) < 3:
        return await message.reply("Խաղը սկսելու համար անհրաժեշտ է նվազագույնը 3 մասնակից:")
    
    game["status"] = "playing"
    
    # Ստանում ենք գաղտնի բառ Gemini-ից
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Տուր մեկ հետաքրքրաշարժ հասարակ առարկայի կամ հասկացության բառ հայերենով (օրինակ՝ խնձոր, ինքնաթիռ, հեռախոս, գիրք), միայն մեկ բառ գրիր առանց հավելյալ տեքստի:"
        )
        secret_word = response.text.strip()
    except Exception:
        secret_word = "Մատիտ"
        
    game["secret_word"] = secret_word
    
    # Լրտեսների քանակի որոշում ըստ կանոնների
    p_count = len(game["players"])
    spy_count = 1 if 3 <= p_count <= 5 else (2 if 6 <= p_count <= 8 else 3)
    
    players_ids = list(game["players"].keys())
    spies = random.sample(players_ids, spy_count)
    game["spies"] = spies
    
    # Ուղարկում ենք դերերը մասնակիցներին անձնական նամակով
    for uid in players_ids:
        try:
            if uid in spies:
                spy_names_str = ", ".join([game['players'][s] for s in spies]) if spy_count > 1 else ""
                spy_info = f" (Միմյանց գիտեք՝ {spy_names_str})" if spy_count > 1 else ""
                theme_spy_name = THEMES[current_theme]["spy"]
                await bot.send_message(uid, f"🤫 Դուք **{theme_spy_name}** եք այս խաղում!{spy_info}", parse_mode="Markdown")
            else:
                await bot.send_message(uid, f"🔑 Գաղտնի բառը՝ **{secret_word}**", parse_mode="Markdown")
        except Exception:
            pass

    await message.reply(
        "🚀 **Խաղը սկսվեց!**\n"
        f"Մասնակիցների քանակը՝ {p_count}, Լրտեսների քանակը՝ {spy_count}\n"
        "Չատում գրելու իրավունքը փակված է մնացածների համար:",
        parse_mode="Markdown"
    )

@dp.message(Command("cancel_game"))
async def cmd_cancel_game(message: types.Message):
    chat_id = message.chat.id
    if chat_id in active_games:
        del active_games[chat_id]
        await message.reply("❌ Խաղը չեղարկվեց:")
    else:
        await message.reply("Ընթացիկ խաղ չկա:")

@dp.message(Command("top_hay_lrtes"))
async def cmd_top(message: types.Message):
    if not users_points:
        return await message.reply("🏆 Դեռևս չկան միավորներ հավաքած մասնակիցներ:")
    
    sorted_top = sorted(users_points.items(), key=lambda x: x[1], reverse=True)[:10]
    top_str = "\n".join([f"{i+1}. ID: {uid} — {pts} միավոր" for i, (uid, pts) in enumerate(sorted_top)])
    await message.reply(f"🏆 **ԹՈՓ 10 ՄԱՍՆԱԿԻՑՆԵՐ**\n\n{top_str}", parse_mode="Markdown")


# --- ԱԴՄԻՆԻ ՀԱՏՈՒԿ ՀՐԱՄԱՆՆԵՐ ---

@dp.message(Command("ban"))
async def admin_ban(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    args = message.text.split()
    if len(args) > 1:
        username = args[1].lstrip('@')
        banned_users.add(username)
        await message.reply(f"🚫 @{username} օգտատերը բլոկավորվեց:")

@dp.message(Command("unban"))
async def admin_unban(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    args = message.text.split()
    if len(args) > 1:
        username = args[1].lstrip('@')
        if username in banned_users:
            banned_users.remove(username)
        await message.reply(f"✅ @{username} օգտատերը հանվեց բլոկից:")

@dp.message(Command("new_year"))
async def admin_theme_ny(message: types.Message):
    global current_theme
    if message.from_user.id != ADMIN_ID: return
    current_theme = "new_year"
    await message.reply("🎄 Ակտիվացավ Ամանորյա ոճը! (Լրտես = ձմեր պապիկ)")

@dp.message(Command("halloween"))
async def admin_theme_hw(message: types.Message):
    global current_theme
    if message.from_user.id != ADMIN_ID: return
    current_theme = "halloween"
    await message.reply("🎃 Ակտիվացավ Հելոինի ոճը! (Լրտես = զոմբի)")

@dp.message(Command("valentin"))
async def admin_theme_val(message: types.Message):
    global current_theme
    if message.from_user.id != ADMIN_ID: return
    current_theme = "valentin"
    await message.reply("❤️ Ակտիվացավ Սիրահարների տոնի ոճը! (Լրտես = վալենտին)")

@dp.message(Command("normal_bot"))
async def admin_theme_norm(message: types.Message):
    global current_theme
    if message.from_user.id != ADMIN_ID: return
    current_theme = "normal"
    await message.reply("🔄 Վերադարձավ ստանդարտ տեսքին:")

@dp.message(Command("text"))
async def admin_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.reply("Գրեք այն տեքստը, որը ցանկանում եք հրապարակել կամ ուղարկել բոտի անունից:")
    await state.set_state(States.waiting_for_admin_broadcast)

@dp.message(States.waiting_for_admin_broadcast)
async def process_admin_broadcast(message: types.Message, state: FSMContext):
    await message.reply(f"📢 **Ադմինի ուղերձ:**\n\n{message.text}", parse_mode="Markdown")
    await state.clear()


# --- ԲՈՏԻ ՀՐԱՄԱՆՆԵՐԻ ՑԱՆԿԻ ԿԱՐԳԱՎՈՐՈՒՄ ---
async def set_bot_commands():
    commands = [
        BotCommand(command="start", description="Գլխավոր մենյու"),
        BotCommand(command="game_hay_lrtes", description="Սկսել լրտես խաղ"),
        BotCommand(command="top_hay_lrtes", description="Թոփ 10 մասնակիցներ"),
        BotCommand(command="cancel_game", description="Չեղարկել խաղը"),
    ]
    await bot.set_my_commands(commands)

if __name__ == "__main__":
    keep_alive()  # Գործարկում ենք Flask սերվերը
    import asyncio
    asyncio.run(set_bot_commands())
    dp.run_polling(bot)
