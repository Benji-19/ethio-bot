import logging
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiohttp import web
import os
from sqlalchemy import create_engine, Column, Integer, String, Text, BigInteger
from sqlalchemy.orm import declarative_base, sessionmaker

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO)

# --- BOT & TOKEN CONFIGURATION ---
# This pulls the token safely from your server settings
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("ERROR: BOT_TOKEN environment variable is missing!")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- DATABASE SETUP ---
DATABASE_URL = "sqlite:///dating_app.db"
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

class LikeRecord(Base):
    __tablename__ = "likes"
    id = Column(Integer, primary_key=True)
    from_tg_id = Column(BigInteger, nullable=False)
    to_tg_id = Column(BigInteger, nullable=False)

Base.metadata.create_all(bind=engine)

# --- FSM STATES FOR REGISTRATION ---
class RegistrationStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_gender = State()
    waiting_for_target_gender = State()
    waiting_for_bio = State()

# --- BOT HANDLERS ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    session = SessionLocal()
    user = session.query(UserProfile).filter(UserProfile.tg_id == message.from_user.id).first()
    session.close()

    if user:
        await message.answer(f"Welcome back, {user.name}! Use /search to find matches.")
    else:
        await message.answer("Welcome to the Ethiopian Dating Bot! Let's create your profile.\nWhat is your name?")
        await state.set_state(RegistrationStates.waiting_for_name)

@dp.message(RegistrationStates.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    kb = [
        [types.KeyboardButton(text="Male"), types.KeyboardButton(text="Female")]
    ]
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=True)
    await message.answer("What is your gender?", reply_markup=keyboard)
    await state.set_state(RegistrationStates.waiting_for_gender)

@dp.message(RegistrationStates.waiting_for_gender)
async def process_gender(message: types.Message, state: FSMContext):
    if message.text not in ["Male", "Female"]:
        await message.answer("Please use the buttons provided to select Male or Female.")
        return
    await state.update_data(gender=message.text)
    kb = [
        [types.KeyboardButton(text="Seeking Male"), types.KeyboardButton(text="Seeking Female")]
    ]
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=True)
    await message.answer("Who are you looking to meet?", reply_markup=keyboard)
    await state.set_state(RegistrationStates.waiting_for_target_gender)

@dp.message(RegistrationStates.waiting_for_target_gender)
async def process_target_gender(message: types.Message, state: FSMContext):
    clean_target = "Male" if "Male" in message.text else "Female"
    await state.update_data(target_gender=clean_target)
    await message.answer("Tell us a bit about yourself (Write your short bio):", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(RegistrationStates.waiting_for_bio)

@dp.message(RegistrationStates.waiting_for_bio)
async def process_bio(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    session = SessionLocal()
    try:
        new_profile = UserProfile(
            tg_id=message.from_user.id,
            name=user_data['name'],
            gender=user_data['gender'],
            target_gender=user_data['target_gender'],
            bio=message.text
        )
        session.merge(new_profile)
        session.commit()
        await message.answer("Your profile is fully registered! Use /search to find Ethiopian singles near you.")
    except Exception as e:
        session.rollback()
        logging.error(f"Database error: {e}")
        await message.answer("An error occurred saving your profile. Please try /start again.")
    finally:
        session.close()
    await state.clear()

@dp.message(Command("search"))
async def cmd_search(message: types.Message):
    session = SessionLocal()
    me = session.query(UserProfile).filter(UserProfile.tg_id == message.from_user.id).first()
    
    if not me:
        await message.answer("Please register first by typing /start")
        session.close()
        return

    # Find users whose gender matches what I am looking for
    match = session.query(UserProfile).filter(
        UserProfile.gender == me.target_gender,
        UserProfile.tg_id != me.tg_id
    ).first()
    session.close()

    if match:
        kb = [
            [types.InlineKeyboardButton(text="❤️ Like", callback_data=f"like_{match.tg_id}")]
        ]
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=kb)
        await message.answer(f"✨ Match Found! ✨\n\n👤 Name: {match.name}\n👫 Gender: {match.gender}\n📝 Bio: {match.bio}", reply_markup=keyboard)
    else:
        await message.answer("No new matches found right now. Check back later!")

@dp.callback_query(F.data.startswith("like_"))
async def handle_like(callback: types.CallbackQuery):
    target_id = int(callback.data.split("_")[1])
    my_id = callback.from_user.id
    
    session = SessionLocal()
    # Check if a mutual like exists
    mutual = session.query(LikeRecord).filter(
        LikeRecord.from_tg_id == target_id,
        LikeRecord.to_tg_id == my_id
    ).first()

    # Save my like
    new_like = LikeRecord(from_tg_id=my_id, to_tg_id=target_id)
    session.add(new_like)
    session.commit()
    session.close()

    await callback.answer("You liked them!")
    
    if mutual:
        await callback.message.answer("🎉 It's a Mutual Match! Start chatting now!")
        try:
            await bot.send_message(target_id, "🎉 Someone you liked just liked you back! Check your matches!")
        except Exception as e:
            logging.error(f"Could not notify target user: {e}")

# --- WEB WEBHOOK SERVER FOR 24/7 UPTIME ---
async def handle_root(request):
    return web.Response(text="Bot is running successfully 24/7!")

async def main():
    # Setup background web server to satisfy hosting platforms
    app = web.Application()
    app.router.add_get('/', handle_root)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    logging.info("Starting Telegram Bot long polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
