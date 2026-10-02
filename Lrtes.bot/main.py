import os
import random
import logging
import threading
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from google import genai

# Կարգավորումներ - Լրացրու այստեղ քո տվյալները
TOKEN = "8929284091:AAFCK5Ke67z6Pciwuo6qYGJ91DBaGhwx7sE"
ADMIN_ID = 6614409372
GEMINI_API_KEY = "GEMINI_API_KEY"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

app = Flask(__name__)
genai_client = genai.Client(api_key=GEMINI_API_KEY)

# Հիշողության բազա
users_db = {}          # user_id -> { 'username': ..., 'score': 0, 'banned': False }
active_games = {}      # chat_id -> game_state
bot_theme = "normal"   # normal, new_year, halloween, valentin

def get_roles():
    if bot_theme == "new_year":
        return {"spy": "Ձմեռ պապիկ", "player": "Ձնծաղիկ", "chat_title": "Ամանորյա Լրտես"}
    elif bot_theme == "halloween":
        return {"spy": "Զոմբի", "player": "Ողջ մնացած", "chat_title": "Հելոինյան Լրտես"}
    elif bot_theme == "valentin":
        return {"spy": "Վալենտին", "player": "Սիրահար", "chat_title": "Սիրո Լրտես"}
    else:
        return {"spy": "Լրտես", "player": "Հասարակ խաղացող", "chat_title": "Հայկական Լրտես"}

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    if user_id not in users_db:
        users_db[user_id] = {"username": message.from_user.username or message.from_user.first_name, "score": 0, "banned": False}
    
    if users_db[user_id]["banned"]:
        await message.answer("Դուք արգելափակված եք այս բոտում:")
        return

    bot_info = await bot.me()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Դոնատ ադմինին", callback_data="donate_admin")],
        [InlineKeyboardButton(text="✉️ Անանուն նամակ ադմինին", callback_data="anon_msg")],
        [InlineKeyboardButton(text="➕ Ավելացնել չատը սեփական բոտում", url=f"https://t.me/{bot_info.username}?startgroup=true")]
    ])
    
    welcome_text = (
        "Բարև ձեզ։ Ես բոտ խաղավարն եմ և օգնում եմ կազմակերպել «Լրտես» խաղը։\n\n"
        "**Խաղի հիմնական կանոնները.**\n"
        "• Մասնակիցների քանակը՝ 3-ից 20 հոգի:\n"
        "• 12 մասնակից անվճար է, մնացած 8-ը պետք է վճարեն 5 աստղ:\n"
        "• Խաղի ընթացքում բոլորը հերթով ասում են մեկական բառ, իսկ լրտեսը փորձում է գուշակել բառը կամ չմատնվել:\n"
        "• Օգտագործեք /game_hay_lrtes խաղը սկսելու համար։"
    )
    await message.answer(welcome_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

@dp.callback_query(lambda c: c.data == "donate_admin")
async def donate_callback(call: types.CallbackQuery):
    await call.message.answer("Ցանկացած քանակությամբ աստղեր նվիրաբերելու համար խնդրում ենք դիմել ադմինին ուղղակիորեն կամ օգտագործել Telegram-ի Stars ֆունկցիան:")
    await call.answer()

@dp.callback_query(lambda c: c.data == "anon_msg")
async def anon_callback(call: types.CallbackQuery):
    await call.message.answer("Գրեք ձեր անանուն նամակը որպես պատասխան այս հաղորդագրությանը, և այն կփոխանցվի ադմինին։")
    await call.answer()

@dp.message(Command("game_hay_lrtes"))
async def cmd_game_init(message: types.Message):
    chat_id = message.chat.id
    if chat_id in active_games:
        await message.answer("Խաղն արդեն սկսված է կամ սպասասրահը բաց է:")
        return

    active_games[chat_id] = {
        "status": "waiting",
        "players": {},
        "paid_count": 0
    }

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Միանալ խաղին", callback_data="join_game")]
    ])
    roles = get_roles()
    await message.answer(f"Արի! {roles['chat_title']} խաղը քեզ է սպասում։\nՍեղմեք ներքևի կոճակը խաղին միանալու համար (Մինիմում՝ 3, Մաքսիմում՝ 20 մասնակից):", reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

@dp.callback_query(lambda c: c.data == "join_game")
async def join_game_callback(call: types.CallbackQuery):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    name = call.from_user.first_name

    if chat_id not in active_games or active_games[chat_id]["status"] != "waiting":
        await call.answer("Խաղը սկսված չէ կամ արդեն ավարտվել է:", show_alert=True)
        return

    game = active_games[chat_id]
    if user_id in game["players"]:
        await call.answer("Դուք արդեն միացել եք խաղին:", show_alert=True)
        return

    if len(game["players"]) >= 20:
        await call.answer("Խաղացողների առավելագույն քանակը լրացել է:", show_alert=True)
        return

    if len(game["players"]) >= 12:
        game["paid_count"] += 1

    game["players"][user_id] = name
    await call.answer("Դուք հաջողությամբ միացաք խաղին!")
    await call.message.edit_text(f"🎮 **{get_roles()['chat_title']}**\nՄիացած մասնակիցներ ({len(game['players'])}/20):\n" + "\n".join([f"• {n}" for n in game["players"].values()]), parse_mode=ParseMode.MARKDOWN, reply_markup=call.message.reply_markup)

@dp.message(Command("start_hay_lrtes"))
async def start_game_process(message: types.Message):
    chat_id = message.chat.id
    if chat_id not in active_games or active_games[chat_id]["status"] != "waiting":
        await message.answer("Սպասասրահ բացված չէ:")
        return

    game = active_games[chat_id]
    if len(game["players"]) < 3:
        await message.answer("Խաղը սկսելու համար անհրաժեշտ է նվազագույնը 3 մասնակից:")
        return

    game["status"] = "playing"
    players = list(game["players"].keys())
    
    p_count = len(players)
    spy_count = 1 if p_count <= 5 else (2 if p_count <= 8 else 3)
    
    spies = random.sample(players, spy_count)
    roles = get_roles()

    try:
        response = genai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents='Գրիր մեկ պարզ հայերեն գոյական (առարկա կամ իր), որը կարող է օգտագործվել Լրտես խաղի համար։ Գրիր միայն բառը, առանց հավելյալ տեքստի։',
        )
        secret_word = response.text.strip()
    except Exception:
        secret_word = "Խնձոր"

    for uid in players:
        try:
            if uid in spies:
                await bot.send_message(uid, f"⚠️ Դուք {roles['spy']} եք այս խաղում։ Գաղտնի բառը չգիտեք։")
            else:
                await bot.send_message(uid, f"Այս խաղի գաղտնի բառն է՝ **{secret_word}**։ Դուք {roles['player']} եք։")
        except:
            pass

    await message.answer(f"Խաղը մեկնարկեց! Լրտեսների քանակը՝ {spy_count}։ Բոլոր մասնակիցներին ուղարկվեցին անձնական հաղորդագրություններ։")

@dp.message(Command("top_hay_lrtes"))
async def show_top(message: types.Message):
    sorted_users = sorted(users_db.items(), key=lambda x: x[1]["score"], reverse=True)[:10]
    text = "🏆 **Թոփ 10 Մասնակիցներ**\n\n"
    for i, (uid, data) in enumerate(sorted_users, 1):
        text += f"{i}. {data['username']} — {data['score']} միավոր\n"
    await message.answer(text, parse_mode=ParseMode.MARKDOWN)

@dp.message(Command("ban"))
async def admin_ban(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Օգտագործումը՝ /ban username")
        return
    target_username = args[1].strip("@")
    for uid, data in users_db.items():
        if data["username"] == target_username:
            data["banned"] = True
            await message.answer(f"Օգտատեր @{target_username} արգելափակվեց:")
            return
    await message.answer("Օգտատերը չի գտնվել:")

@dp.message(Command("unban"))
async def admin_unban(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Օգտագործումը՝ /unban username")
        return
    target_username = args[1].strip("@")
    for uid, data in users_db.items():
        if data["username"] == target_username:
            data["banned"] = False
            await message.answer(f"Օգտատեր @{target_username} հանվեց արգելափակումից:")
            return
    await message.answer("Օգտատերը չի գտնվել:")

@dp.message(Command("new_year"))
async def theme_new_year(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    global bot_theme
    bot_theme = "new_year"
    await message.answer("🎄 Ամանորյա ոճն ակտիվացված է։ Լրտեսը այժմ Ձմեռ պապիկ է։")

@dp.message(Command("halloween"))
async def theme_halloween(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    global bot_theme
    bot_theme = "halloween"
    await message.answer("🎃 Հելոինյան ոճն ակտիվացված է։ Լրտեսը այժմ Զոմբի է։")

@dp.message(Command("valentin"))
async def theme_valentin(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    global bot_theme
    bot_theme = "valentin"
    await message.answer("💖 Սիրահարների տոնի ոճն ակտիվացված է։ Լրտեսը այժմ Վալենտին է։")

@dp.message(Command("normal_bot"))
async def theme_normal(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    global bot_theme
    bot_theme = "normal"
    await message.answer("🔄 Բոտը վերադարձավ իր նորմալ տեսքին։")

@dp.message(Command("text"))
async def admin_text(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    text_to_send = message.text.replace("/text", "").strip()
    if text_to_send:
        await message.answer(f"📢 **Հայտարարություն ադմինից:**\n\n{text_to_send}", parse_mode=ParseMode.MARKDOWN)

# Flask վեբ սերվեր Render-ի համար
@app.route("/")
def index():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # Գործարկում ենք Flask-ը առանձին թրեդով, որպեսզի չարգելափակի բոտի աշխատանքը
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    # Գործարկում ենք Telegram բոտը (Polling)
    import asyncio
    asyncio.run(dp.start_polling(bot))
