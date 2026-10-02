import asyncio
import logging
import random
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    LabeledPrice, Message
)
from google import genai
from config import BOT_TOKEN, ADMIN_ID, GEMINI_API_KEY

# Լոգավորման կարգավորում
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# --- GEMINI AI ԿԱՐԳԱՎՈՐՈՒՄ ---
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY and GEMINI_API_KEY != "ՁԵՐ_GEMINI_API_ԿԵՅԸ_ԱՅՍՏԵՂ" else None

# --- FSM (Վիճակների մեքենա) ---
class AdminContactStates(StatesGroup):
    waiting_for_message = State()
    waiting_for_stars_amount = State()
    waiting_for_ai_prompt = State()

# --- ՀԻՇՈՂՈՒԹՅՈՒՆ ԵՎ ԿԱՐԳԱՎՈՐՈՒՄՆԵՐ ---
active_games = {}
current_theme = "normal"  # normal, new_year, valentine, halloween

# Տոնական թեմաների վայրերի բազաներ և դիզայն
THEMES_DATA = {
    "normal": {
        "name": "🌟 Ստանդարտ (Normal)",
        "locations": [
            "Բանկ", "Ինքնաթիռ", "Հիվանդանոց", "Ռեստորան", "Սուպերմարկետ",
            "Տիեզերակայան", "Ոստիկանություն", "Կազինո", "Զինվորական բազա", 
            "Դպրոց", "Կինոթատրոն", "Նավահանգիստ", "Հյուրանոց"
        ]
    },
    "new_year": {
        "name": "🎄 Ամանորյա (New Year)",
        "locations": [
            "Ձնեմարդու արհեստանոց", "Ձմեռ պապի նստավայր", "Տոնածառի տոնավաճառ",
            "Սահնակների ավտոտնակ", "Նվերների փաթեթավորման բաժին", "Տաք շոկոլադի սրճարան",
            "Սահադաշտ", "Ամանորյա հրավառության դաշտ", "Հյուսիսային բևեռի փոստ"
        ]
    },
    "valentine": {
        "name": "💖 Սուրբ Վալենտին (Valentine's Day)",
        "locations": [
            "Ռոմանտիկ սրճարան", "Ծաղկի խանութ", "Սրտաձև շոկոլադի ֆաբրիկա",
            "Համբույրների կամուրջ", "Աստղադիտարան", "Գաղտնի նամակների արխիվ",
            "Վարդերի այգի", "Ամհարսանքի սրահ", "Սիրային զբոսանավ"
        ]
    },
    "halloween": {
        "name": "🎃 Հելոուին (Halloween)",
        "locations": [
            "Հին Լքված Աղջկա Անտուն Տուն", "Վամպիրների Ամրոց", "Կախարդների Խոհանոց",
            "Գերեզմանոց գիշերով", "Դդմե դաշտ", "Ուրվականների հյուրանոց",
            "Զոմբիների լաբորատորիա", "Մութ անտառ", "Սատանայական ջրաղաց"
        ]
    }
}

# --- ՄԵՆՅՈՒՆԵՐ ---
def get_main_menu():
    theme_info = THEMES_DATA[current_theme]["name"]
    keyboard = [
        [InlineKeyboardButton(text="🤖 Զրույց Gemini AI-ի հետ", callback_data="gemini_chat_start")],
        [InlineKeyboardButton(text="💌 Անանուն նամակ ադմինին", callback_data="send_anon")],
        [InlineKeyboardButton(text="⭐ Դոնատ ադմինին (Stars)", callback_data="donate_start")],
        [InlineKeyboardButton(text=f"🎭 Թեմա: {theme_info}", callback_data="change_theme_menu")],
        [InlineKeyboardButton(text="🎮 Ինչպես խաղալ Լրտես", callback_data="help_spy")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_back_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Վերադառնալ մենյու", callback_data="back_to_menu")]
    ])

# --- /START ՀՐԱՄԱՆ ---
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    if message.chat.type == "private":
        await message.answer(
            "Բարև ձեզ 👋!\n"
            "Սա բազմաֆունկցիոնալ բոտ է **«Լրտես»** խաղի, Google Gemini AI զրույցի, անանուն նամակների և ադմինին դոնատի համար։\n\n"
            f"Ընթացիկ թեման՝ **{THEMES_DATA[current_theme]['name']}**\n\n"
            "Ընտրեք գործողությունը ստորև 👇",
            reply_markup=get_main_menu()
        )
    else:
        await message.answer(f"Բոտը պատրաստ է 🕵️‍♂️ (Թեմա՝ {THEMES_DATA[current_theme]['name']})! Խմբում խաղ սկսելու համար գրեք `/spy`:")

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Գլխավոր մենյու 👇", reply_markup=get_main_menu())
    await callback.answer()


# --- GEMINI AI ԻՆՏԵԳՐԱՑԻԱ ---
@dp.callback_query(F.data == "gemini_chat_start")
async def gemini_chat_start(callback: types.CallbackQuery, state: FSMContext):
    if not client:
        await callback.answer("❌ Gemini API Key-ը կարգավորված չէ config.py ֆայլում:", show_alert=True)
        return

    await state.set_state(AdminContactStates.waiting_for_ai_prompt)
    await callback.message.edit_text(
        "🤖 **Google Gemini AI Զրույց**\n\n"
        "Գրեք ձեր հարցը, խնդրանքը կամ տեքստը, և ինտելեկտուալ բոտը անմիջապես կպատասխանի ձեզ 👇",
        reply_markup=get_back_menu()
    )
    await callback.answer()

@dp.message(AdminContactStates.waiting_for_ai_prompt)
async def process_gemini_prompt(message: Message, state: FSMContext):
    if not client:
        await message.answer("❌ AI սերվերը հասանելի չէ:", reply_markup=get_main_menu())
        await state.clear()
        return

    user_text = message.text
    if not user_text:
        await message.answer("Խնդրում եմ ուղարկել տեքստային հարց:")
        return

    waiting_msg = await message.answer("⏳ Gemini-ն մտածում է պատասխանը...")

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_text,
        )
        ai_reply = response.text
        
        await bot.delete_message(chat_id=message.chat.id, message_id=waiting_msg.message_id)
        await message.answer(
            f"🤖 **Gemini պատասխանը:**\n\n{ai_reply}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Հարցնել ևս մեկը", callback_data="gemini_chat_start")],
                [InlineKeyboardButton(text="⬅️ Վերադառնալ մենյու", callback_data="back_to_menu")]
            ])
        )
    except Exception as e:
        logging.error(f"Gemini Error: {e}")
        await bot.delete_message(chat_id=message.chat.id, message_id=waiting_msg.message_id)
        await message.answer("❌ AI-ի հետ կապվելիս սխալ տեղի ունեցավ: Փորձեք ավելի ուշ։", reply_markup=get_main_menu())
        await state.clear()


# --- ԹԵՄԱՆԵՐԻ ԿԱՌԱՎԱՐՈՒՄ ---
@dp.callback_query(F.data == "change_theme_menu")
async def change_theme_menu_handler(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌟 Ստանդարտ", callback_data="set_theme_normal")],
        [InlineKeyboardButton(text="🎄 Ամանոր", callback_data="set_theme_new_year")],
        [InlineKeyboardButton(text="💖 Վալենտին", callback_data="set_theme_valentine")],
        [InlineKeyboardButton(text="🎃 Հելոուին", callback_data="set_theme_halloween")],
        [InlineKeyboardButton(text="⬅️ Վերադառնալ", callback_data="back_to_menu")]
    ])
    await callback.message.edit_text(
        "Ընտրեք խաղի և բոտի տոնական թեման 👇\n"
        f"(Գործող թեմա՝ **{THEMES_DATA[current_theme]['name']}**)",
        reply_markup=keyboard
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("set_theme_"))
async def set_theme_handler(callback: types.CallbackQuery):
    global current_theme
    theme_key = callback.data.replace("set_theme_", "")
    if theme_key in THEMES_DATA:
        current_theme = theme_key
        await callback.answer(f"✅ Թեման փոխվեց՝ {THEMES_DATA[current_theme]['name']}")
    
    await callback.message.edit_text(
        f"Գլխավոր մենյու:\nԸնթացիկ թեմա՝ **{THEMES_DATA[current_theme]['name']}**",
        reply_markup=get_main_menu()
    )


# --- ԻՆՉՊԵՍ ԽԱՂԱԼ ---
@dp.callback_query(F.data == "help_spy")
async def help_spy_handler(callback: types.CallbackQuery):
    text = (
        "🕵‍♂️ **Ինչպես խաղալ Լրտես (Spyfall):**\n\n"
        "1. Ավելացրեք բոտը խմբային չատին:\n"
        "2. Խմբում գրեք `/spy` հրամանը։\n"
        "3. Մասնակիցները սեղմում են «Միանալ խաղին»։\n"
        "4. Սեղմեք «Սկսել խաղը», և բոտը անձնական նամակով կուղարկի գաղտնի վայրը՝ կախված ընտրված տոնական թեմայից!"
    )
    await callback.message.edit_text(text, reply_markup=get_back_menu())
    await callback.answer()


# --- ԱՆԱՆՈՒՆ ՆԱՄԱԿՆԵՐԻ ՀԱՄԱԿԱՐԳ ---
@dp.callback_query(F.data == "send_anon")
async def start_anon_message(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminContactStates.waiting_for_message)
    await callback.message.edit_text(
        "Գրեք ձեր անանուն նամակը ադմինին (կարող եք ուղարկել նաև նկար/տեքստ) 👇\n\n"
        "Ադմինը կստանա նամակը ձեր նիկնեյմով և ID-ով:",
        reply_markup=get_back_menu()
    )
    await callback.answer()

@dp.message(AdminContactStates.waiting_for_message)
async def process_anon_message(message: Message, state: FSMContext):
    user = message.from_user
    username_str = f"@{user.username}" if user.username else "Չկա username"
    
    admin_text = (
        "📩 **Նոր անանուն նամակ օգտատերից:**\n\n"
        f"👤 **Անուն:** {user.full_name}\n"
        f"🔗 **Username:** {username_str}\n"
        f"🆔 **User ID:** `{user.id}`\n\n"
        f"💬 **Նամակը:**"
    )
    
    try:
        await bot.send_message(ADMIN_ID, admin_text)
        await message.send_copy(chat_id=ADMIN_ID)
        await message.answer("✅ Ձեր նամակը հաջողությամբ ուղարկվեց ադմինին:", reply_markup=get_main_menu())
    except Exception as e:
        logging.error(f"Error: {e}")
        await message.answer("❌ Չհաջողվեց ուղարկել նամակը:", reply_markup=get_main_menu())
    
    await state.clear()


# --- ԴՈՆԱՏԻ ՀԱՄԱԿԱՐԳ (TELEGRAM STARS) ---
@dp.callback_query(F.data == "donate_start")
async def start_donation(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminContactStates.waiting_for_stars_amount)
    await callback.message.edit_text(
        "⭐ **Դոնատ ադմինին**\n\n"
        "Մուտքագրեք աստղերի քանակը, որոնք ցանկանում եք նվիրաբերել (օրինակ՝ `10`, `50`, `100`):",
        reply_markup=get_back_menu()
    )
    await callback.answer()

@dp.message(AdminContactStates.waiting_for_stars_amount)
async def process_stars_amount(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Խնդրում եմ մուտքագրել միայն թիվ (օրինակ՝ 10):")
        return

    amount = int(message.text)
    if amount < 1:
        await message.answer("❌ Աստղերի քանակը պետք է մեծ լինի 0-ից:")
        return

    await state.clear()
    prices = [LabeledPrice(label="Աջակցություն ադմինին (Stars)", amount=amount)]
    
    await message.answer_invoice(
        title="⭐ Դոնատ ադմինին",
        description=f"Շնորհակալություն աջակցության համար ({amount} աստղ)",
        prices=prices,
        payload=f"donation_{message.from_user.id}_{amount}",
        currency="XTR",
        provider_token="",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💳 Վճարել {amount} ⭐", pay=True)],
            [InlineKeyboardButton(text="⬅️ Չեղարկել", callback_data="back_to_menu")]
        ])
    )

@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    payment_info = message.successful_payment
    total_amount = payment_info.total_amount
    user = message.from_user
    
    await message.answer(f"🎉 Շնորհակալություն! Դուք հաջողությամբ նվիրաբերեցիք {total_amount} ⭐")
    
    admin_msg = (
        f"💰 **Նոր դոնատ Telegram Stars-ով!**\n\n"
        f"👤 **Օգտատեր:** {user.full_name} (@{user.username or 'չկա'})\n"
        f"🆔 **ID:** `{user.id}`\n"
        f"⭐ **Գումար:** {total_amount} աստղ"
    )
    await bot.send_message(ADMIN_ID, admin_msg)


# --- ԽՄԲԱՅԻՆ «ԼՐՏԵՍ» ԽԱՂ ---
@dp.message(Command("spy"))
async def cmd_spy_start(message: Message):
    if message.chat.type == "private":
        await message.answer("❌ Այս հրամանը նախատեսված է միայն խմբային չատերի համար:")
        return

    chat_id = message.chat.id
    if chat_id in active_games and active_games[chat_id]["status"] == "playing":
        await message.answer("⚠️ Այս չատում արդեն ընթանում է խաղ:")
        return

    active_games[chat_id] = {"players": [], "status": "waiting"}

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🙋‍♂️ Միանալ խաղին", callback_data="spy_join")],
        [InlineKeyboardButton(text="🚀 Սկսել խաղը", callback_data="spy_start_game")]
    ])

    theme_name = THEMES_DATA[current_theme]["name"]
    await message.answer(
        f"🕵️‍♂ **«Լրտես» խաղը սկսվում է!**\n"
        f"🎭 **Թեմա:** {theme_name}\n\n"
        "Մասնակցելու համար սեղմեք **«Միանալ խաղին»** կոճակը։\n"
        "Երբ բոլորը հավաքվեն, սեղմեք **«Սկսել խաղը»**:",
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "spy_join")
async def spy_join_handler(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    user_name = callback.from_user.first_name

    if chat_id not in active_games or active_games[chat_id]["status"] != "waiting":
        await callback.answer("❌ Ակտիվ սպասման փուլով խաղ չկա:", show_alert=True)
        return

    players = active_games[chat_id]["players"]
    if user_id in players:
        await callback.answer("⚠️ Դուք արդեն միացել եք խաղին:", show_alert=True)
        return

    players.append(user_id)
    await callback.answer(f"✅ {user_name}, դուք միացաք խաղին!")

    try:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"🙋‍♂️ Միանալ խաղին ({len(players)})", callback_data="spy_join")],
            [InlineKeyboardButton(text="🚀 Սկսել խաղը", callback_data="spy_start_game")]
        ])
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception:
        pass

@dp.callback_query(F.data == "spy_start_game")
async def spy_start_game_handler(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id

    if chat_id not in active_games or active_games[chat_id]["status"] != "waiting":
        await callback.answer("❌ Հնարավոր չէ սկսել խաղը:", show_alert=True)
        return

    players = active_games[chat_id]["players"]
    if len(players) < 3:
        await callback.answer("❌ Հարկավոր է առնվազն 3 մասնակից:", show_alert=True)
        return

    active_games[chat_id]["status"] = "playing"
    
    locations_list = THEMES_DATA[current_theme]["locations"]
    chosen_location = random.choice(locations_list)
    spy_id = random.choice(players)

    for player_id in players:
        try:
            if player_id == spy_id:
                await bot.send_message(
                    player_id, 
                    "🕵️‍♂️ **Դուք ԼՐՏԵՍՆ եք!**\n\nՓորձեք գուշակել վայրը կամ չբացահայտվել:"
                )
            else:
                await bot.send_message(
                    player_id, 
                    f"📍 **Գաղտնի վայրը ({THEMES_DATA[current_theme]['name']}):** `{chosen_location}`\n\nԳտեք լրտեսին՝ տալով հարցեր միմյանց:"
                )
        except Exception:
            pass

    await callback.message.edit_text(
        f"🎮 **Խաղը սկսված է!** ({THEMES_DATA[current_theme]['name']})\n\n"
        f"👥 Մասնակիցներ՝ `{len(players)}` հոգի\n"
        "📩 Դերերն ուղարկվեցին անձնական չատերով։"
    )
    del active_games[chat_id]
    await callback.answer()


# --- ԲՈՏԻ ԳՈՐԾԱՐԿՈՒՄ ---
async def main():
    print("Բոտը հաջողությամբ միացավ և աշխատում է...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
