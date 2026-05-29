import logging
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiohttp import web  # 🌐 Added to give Render the web port it wants
from sqlalchemy import create_engine, Column, Integer, String, Text, BigInteger
from sqlalchemy.orm import declarative_base, sessionmaker

# --- CONFIGURATION ---
TOKEN = "8936925896:AAGuDSActdT9UKs_SONbbYS9OhEXfr__26c"
DATABASE_URL = "sqlite:///dating_app.db"

bot = Bot(token=TOKEN)
logging.basicConfig(level=logging.INFO)
dp = Dispatcher()

# --- DATABASE SETUP ---
Base = declarative_base()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

class UserProfile(Base):
    __tablename__ = "profiles"
    id = Column(Integer, primary_key=True)
    tg_id = Column(BigInteger, unique=True, nullable=False)
    name = Column(String(100))
    gender = Column(String(20))
    target_gender = Column(String(20))
    bio = Column(Text)
    language = Column(String(5), default="en")

class LikeRecord(Base):
    __tablename__ = "likes"
    id = Column(Integer, primary_key=True)
    from_tg_id = Column(BigInteger, nullable=False)
    to_tg_id = Column(BigInteger, nullable=False)

Base.metadata.create_all(bind=engine)

class RegistrationStates(StatesGroup):
    language = State()
    name = State()
    gender = State()
    target_gender = State()
    bio = State()

TEXTS = {
    "en": {
        "welcome": "Welcome to Let's Meet New People! ✨\nDiscover meaningful connections instantly.",
        "choose_lang": "Please select your preferred language:",
        "ask_name": "What is your name?",
        "ask_gender": "What is your gender?",
        "ask_target": "Who are you looking to meet?",
        "ask_bio": "Tell us a little about yourself (Bio or friend chat preferences):",
        "male": "Male 🧑", "female": "Female 👩", "both": "Everyone 🌐",
        "profile_saved": "Your profile has been saved successfully! 🎉",
        "main_menu": "What would you like to do?",
        "btn_browse": "Discover Profiles 🔍", "btn_my_profile": "My Profile 👤", "btn_edit_profile": "Edit My Profile ⚙️",
        "like": "❤️", "next": "❌", "no_profiles": "No new profiles found matching your preferences right now. Check back soon!",
        "match_alert": "🔔 *Someone just liked your profile!*\nTap 'Discover Profiles 🔍' right now to find out who it is! 😉"
    },
    "am": {
        "welcome": "ወደ Let's Meet New People በደህና መጡ! ✨\nእውነተኛ ግንኙነቶችን እዚህ ያግኙ።",
        "choose_lang": "እባክዎን የሚመርትን ቋንቋ ይምረጡ፦",
        "ask_name": "ስምዎ ማን ይባላል?", "ask_gender": "ጾታዎ ምንድነው?", "ask_target": "ማንኛውን ማግኘት ይፈልጋሉ?", "ask_bio": "ስለራስዎ በጥቂቱ ይንገሩን (ባዮ)፦",
        "male": "ወንድ 🧑", "female": "ሴት 👩", "both": "ሁሉንም 🌐",
        "profile_saved": "የእርስዎ መገለጫ በተሳካ ሁኔታ ተቀምጧል! 🎉",
        "main_menu": "ምን ማድረግ ይፈልጋሉ?",
        "btn_browse": "ሰዎችን ፈልግ 🔍", "btn_my_profile": "የእኔ መገለጫ 👤", "btn_edit_profile": "መገለጫዬን ቀይር ⚙️",
        "like": "❤️", "next": "❌", "no_profiles": "በአሁኑ ጊዜ ከእርስዎ ምርጫ ጋር የሚዛመዱ አዳዲስ መገለጫዎች አልተገኙም። ቆይተው እንደገና ይሞክሩ!",
        "match_alert": "🔔 *አንድ ሰው መገለጫዎን ወዶታል!*\nማን እንደሆነ ለማወቅ አሁኑኑ 'ሰዎችን ፈልግ 🔍' የሚለውን ይጫኑ! 😉"
    }
}

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    db = SessionLocal()
    user = db.query(UserProfile).filter(UserProfile.tg_id == message.from_user.id).first()
    db.close()
    if user: await show_main_menu(message, user.language)
    else: await start_registration_flow(message, state)

async def start_registration_flow(message: types.Message, state: FSMContext):
    builder = ReplyKeyboardBuilder()
    builder.button(text="English 🇬🇧")
    builder.button(text="አማርኛ 🇪🇹")
    await message.answer(TEXTS["en"]["welcome"] + "\n\n" + TEXTS["en"]["choose_lang"], reply_markup=builder.as_markup(resize_keyboard=True))
    await state.set_state(RegistrationStates.language)

@dp.message(RegistrationStates.language)
async def process_language(message: types.Message, state: FSMContext):
    lang = "en" if "English" in message.text else "am"
    await state.update_data(language=lang)
    await message.answer(TEXTS[lang]["ask_name"], reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(RegistrationStates.name)

@dp.message(RegistrationStates.name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    data = await state.get_data(); lang = data["language"]
    builder = ReplyKeyboardBuilder()
    builder.button(text=TEXTS[lang]["male"])
    builder.button(text=TEXTS[lang]["female"])
    await message.answer(TEXTS[lang]["ask_gender"], reply_markup=builder.as_markup(resize_keyboard=True))
    await state.set_state(RegistrationStates.gender)

@dp.message(RegistrationStates.gender)
async def process_gender(message: types.Message, state: FSMContext):
    data = await state.get_data(); lang = data["language"]
    gender_val = "Male" if message.text == TEXTS[lang]["male"] else "Female"
    await state.update_data(gender=gender_val)
    builder = ReplyKeyboardBuilder()
    builder.button(text=TEXTS[lang]["male"])
    builder.button(text=TEXTS[lang]["female"])
    builder.button(text=TEXTS[lang]["both"])
    await message.answer(TEXTS[lang]["ask_target"], reply_markup=builder.as_markup(resize_keyboard=True))
    await state.set_state(RegistrationStates.target_gender)

@dp.message(RegistrationStates.target_gender)
async def process_target(message: types.Message, state: FSMContext):
    data = await state.get_data(); lang = data["language"]
    target_val = "Everyone"
    if message.text == TEXTS[lang]["male"]: target_val = "Male"
    elif message.text == TEXTS[lang]["female"]: target_val = "Female"
    await state.update_data(target_gender=target_val)
    await message.answer(TEXTS[lang]["ask_bio"], reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(RegistrationStates.bio)

@dp.message(RegistrationStates.bio)
async def process_bio(message: types.Message, state: FSMContext):
    data = await state.get_data(); lang = data["language"]
    db = SessionLocal()
    new_user = UserProfile(tg_id=message.from_user.id, name=data["name"], gender=data["gender"], target_gender=data["target_gender"], bio=message.text, language=lang)
    db.merge(new_user); db.commit(); db.close()
    await message.answer(TEXTS[lang]["profile_saved"])
    await state.clear(); await show_main_menu(message, lang)

async def show_main_menu(message: types.Message, lang: str):
    builder = ReplyKeyboardBuilder()
    builder.button(text=TEXTS[lang]["btn_browse"])
    builder.button(text=TEXTS[lang]["btn_my_profile"])
    builder.button(text=TEXTS[lang]["btn_edit_profile"])
    builder.adjust(2, 1)
    await message.answer(TEXTS[lang]["main_menu"], reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(F.text.in_([TEXTS["en"]["btn_edit_profile"], TEXTS["am"]["btn_edit_profile"]]))
async def manual_edit_profile(message: types.Message, state: FSMContext):
    await state.clear(); await start_registration_flow(message, state)

@dp.message(F.text.in_([TEXTS["en"]["btn_my_profile"], TEXTS["am"]["btn_my_profile"]]))
async def show_own_profile(message: types.Message):
    db = SessionLocal(); user = db.query(UserProfile).filter(UserProfile.tg_id == message.from_user.id).first(); db.close()
    if not user: return
    profile_card = f"👤 *YOUR PROFILE CARD*\n━━━━━━━━━━━━━━━━━━━━\n👤 *Name:* {user.name}\n🧑 *Gender:* {user.gender}\n🎯 *Looking For:* {user.target_gender}\n📝 *Bio:* _{user.bio}_\n━━━━━━━━━━━━━━━━━━━━"
    await message.answer(profile_card, parse_mode="Markdown")

@dp.message(F.text.in_([TEXTS["en"]["btn_browse"], TEXTS["am"]["btn_browse"]]))
async def browse_profiles(message: types.Message):
    db = SessionLocal(); current_user = db.query(UserProfile).filter(UserProfile.tg_id == message.from_user.id).first()
    if not current_user: db.close(); return
    already_liked = [like.to_tg_id for like in db.query(LikeRecord).filter(LikeRecord.from_tg_id == current_user.tg_id).all()]
    query = db.query(UserProfile).filter(UserProfile.tg_id != current_user.tg_id, ~UserProfile.tg_id.in_(already_liked))
    if current_user.target_gender != "Everyone": query = query.filter(UserProfile.gender == current_user.target_gender)
    next_profile = query.first(); db.close(); lang = current_user.language
    if not next_profile: await message.answer(TEXTS[lang]["no_profiles"]); return
    profile_card = f"✨ *NEW CANDIDATE MATCH FOUND!* ✨\n━━━━━━━━━━━━━━━━━━━━\n👤 *Name:* {next_profile.name}\n🧑 *Gender:* {next_profile.gender}\n📝 *About:* _{next_profile.bio}_\n━━━━━━━━━━━━━━━━━━━━"
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text=TEXTS[lang]["like"], callback_data=f"like_{next_profile.tg_id}"), types.InlineKeyboardButton(text=TEXTS[lang]["next"], callback_data="next_profile"))
    await message.answer(profile_card, parse_mode="Markdown", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("like_"))
async def handle_like_callback(callback: types.CallbackQuery):
    target_id = int(callback.data.split("_")[1]); db = SessionLocal()
    new_like = LikeRecord(from_tg_id=callback.from_user.id, to_tg_id=target_id); db.add(new_like); db.commit()
    target_user = db.query(UserProfile).filter(UserProfile.tg_id == target_id).first(); db.close()
    if target_user:
        try: await bot.send_message(chat_id=target_id, text=TEXTS[target_user.language]["match_alert"], parse_mode="Markdown")
        except Exception: pass
    await callback.answer(); await browse_profiles(callback.message)

@dp.callback_query(F.data == "next_profile")
async def handle_next_callback(callback: types.CallbackQuery):
    await callback.answer(); await browse_profiles(callback.message)

# 🌐 --- THE WEB LAYER RENDER DEMANDS ---
async def handle_home(request):
    return web.Response(text="Bot is perfectly alive!")

async def main():
    # 1. Start a fake web app on port 10000 so Render treats it like a real website
    app = web.Application()
    app.router.add_get("/", handle_home)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 10000)
    await site.start()
    
    # 2. Run your Telegram bot loop right next to it
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())