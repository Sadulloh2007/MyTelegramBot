import asyncio
import logging
import json
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, 
    ReplyKeyboardMarkup, 
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

API_TOKEN = "7637477116:AAHCuE3f7lVXmw6uMSlObP5-PKLRITzoHw4"
ADMIN_ID = 8164159044
CHAT_LINK = "https://t.me/Almas24_Bot"

# Файл для хранения товаров
PRODUCTS_FILE = "products.json"

def load_products():
    if os.path.exists(PRODUCTS_FILE):
        with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    else:
        # Начальные товары
        return {
            "100 💎": 12,
            "200 💎": 24,
            "Пропуск прокачка🏷": 35
        }

def save_products():
    with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=4)

# Загружаем товары при запуске
products = load_products()

# Остальные базы данных
users = {}
# Реферальная система: ключ — ID реферера, значение — список ID приглашённых пользователей
referrals = {}
promocodes = {
    "ALMAZ": 10,  # Пример промокода (6 символов, заглавные буквы)
    "VIPFR": 100
}
pending_payments = {}
reviews = []
statistics = {
    "total_users": 0,
    "total_orders": 0,
    "start_date": datetime.now().strftime("%d.%m.%Y %H:%M")
}

class States(StatesGroup):
    choosing_product = State()
    entering_player_id = State()
    entering_promocode = State()
    waiting_payment = State()
    waiting_question = State()
    admin_add_product = State()
    admin_delete_product = State()
    admin_add_promo = State()

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# Проверка админа
async def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

# Уведомление о новом пользователе
async def notify_admin(new_user: types.User, referral_info: str = ""):
    msg = (f"🆕 Новый пользователь: @{new_user.username}\n"
           f"ID: {new_user.id}\n"
           f"Дата регистрации: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    if referral_info:
        msg += f"\nРеферал: {referral_info}"
    await bot.send_message(ADMIN_ID, msg)

# Обработка аргументов команды /start для реферальной системы
def process_referral(message: Message):
    text = message.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) > 1:
        arg = parts[1].strip()
        if arg.isdigit():
            return int(arg)
    return None

# Формируем главное меню (для пользователя или админа)
def get_main_menu(user_id: int) -> ReplyKeyboardMarkup:
    if user_id == ADMIN_ID:
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🛒 Купить"), KeyboardButton(text="💬 Поддержка")],
                [KeyboardButton(text="👥 Рефералка"), KeyboardButton(text="👑 Админ-панель")]
            ],
            resize_keyboard=True
        )
    else:
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🛒 Купить"), KeyboardButton(text="💬 Поддержка")],
                [KeyboardButton(text="👥 Рефералка")]
            ],
            resize_keyboard=True
        )

# Команда старта
@dp.message(Command("start"))
async def start_cmd(message: Message, state: FSMContext):
    try:
        await state.clear()
        user_id = message.from_user.id

        referrer_id = process_referral(message)
        referral_info = ""

        # Регистрация нового пользователя
        if user_id not in users:
            users[user_id] = {
                "username": message.from_user.username,
                "reg_date": datetime.now().strftime("%d.%m.%Y %H:%M"),
                "orders": 0,
                "referred_by": referrer_id,
            }
            statistics["total_users"] += 1
            if referrer_id and referrer_id != user_id:
                referrals.setdefault(referrer_id, []).append(user_id)
                referral_info = f"Пришел по реферальной ссылке от {referrer_id}"
            await notify_admin(message.from_user, referral_info)

        kb = get_main_menu(user_id)
        await message.answer("Привет! Выберите действие:", reply_markup=kb)

    except Exception as e:
        logger.error(f"Start error: {e}")

# Рефералька — вывод информации о рефералах
@dp.message(F.text == "👥 Рефералка")
async def referral_info(message: Message):
    user_id = message.from_user.id
    ref_link = f"{CHAT_LINK}?start={user_id}"
    count = len(referrals.get(user_id, []))
    await message.answer(
        f"Ваш реферальный код:\n/start {user_id}\nВаша ссылка: {ref_link}\nПриглашено: {count} пользователей"
    )

# Админ-панель
@dp.message(F.text == "👑 Админ-панель")
async def admin_panel(message: Message):
    if await is_admin(message.from_user.id):
        kb = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="➕ Добавить товар"), KeyboardButton(text="🗑 Удалить товар")],
            [KeyboardButton(text="🎫 Добавить промокод")],
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="📝 Отзывы")]
        ], resize_keyboard=True)
        await message.answer("Админ-панель:", reply_markup=kb)

# Добавление товара
@dp.message(F.text == "➕ Добавить товар")
async def add_product_start(message: Message, state: FSMContext):
    if await is_admin(message.from_user.id):
        await state.set_state(States.admin_add_product)
        await message.answer("Введите название и цену товара в формате:\nНазвание - Цена")

@dp.message(States.admin_add_product)
async def add_product_finish(message: Message, state: FSMContext):
    try:
        name, price = message.text.split(" - ")
        products[name.strip()] = int(price)
        save_products()
        await message.answer(f"✅ Товар добавлен:\n{name.strip()} - {price} сомони")
        await state.clear()
    except Exception as e:
        await message.answer("❌ Неверный формат! Пример:\nНазвание товара - 100")
        logger.error(f"Add product error: {e}")

# Удаление товара
@dp.message(F.text == "🗑 Удалить товар")
async def delete_product_start(message: Message, state: FSMContext):
    if await is_admin(message.from_user.id):
        if not products:
            return await message.answer("❌ Нет товаров для удаления.")
        product_list = "\n".join(products.keys())
        await state.set_state(States.admin_delete_product)
        await message.answer(f"Введите название товара для удаления:\n{product_list}")

@dp.message(States.admin_delete_product)
async def delete_product_finish(message: Message, state: FSMContext):
    try:
        product_name = message.text.strip()
        if product_name in products:
            del products[product_name]
            save_products()
            await message.answer(f"✅ Товар '{product_name}' удален.")
        else:
            await message.answer("❌ Товар не найден.")
        await state.clear()
    except Exception as e:
        await message.answer("❌ Произошла ошибка при удалении товара.")
        logger.error(f"Delete product error: {e}")

# Добавление промокода (админ)
@dp.message(F.text == "🎫 Добавить промокод")
async def add_promo_start(message: Message, state: FSMContext):
    if await is_admin(message.from_user.id):
        await state.set_state(States.admin_add_promo)
        await message.answer("Введите промокод и скидку в формате:\nКОД - ПРОЦЕНТ\nПромокод должен состоять из 6 заглавных букв.")

@dp.message(States.admin_add_promo)
async def add_promo_finish(message: Message, state: FSMContext):
    try:
        code, discount = message.text.split(" - ")
        code = code.strip()
        if not (code.isalpha() and code.isupper() and len(code) == 6):
            return await message.answer("❌ Неверный формат промокода! Он должен состоять из 6 заглавных букв.")
        promocodes[code] = int(discount)
        await message.answer(f"✅ Промокод добавлен:\n{code} - {discount}%")
        await state.clear()
    except Exception as e:
        await message.answer("❌ Неверный формат! Пример:\nPROMO - 15")
        logger.error(f"Add promo error: {e}")

# Просмотр статистики
@dp.message(F.text == "📊 Статистика")
async def show_stats(message: Message):
    if await is_admin(message.from_user.id):
        stats_text = (
            f"📊 Статистика бота\n\n"
            f"👥 Пользователей: {statistics['total_users']}\n"
            f"🛒 Заказов: {statistics['total_orders']}\n"
            f"📅 Запущен: {statistics['start_date']}\n"
            f"🔄 Последнее обновление: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        await message.answer(stats_text)

# Просмотр отзывов
@dp.message(F.text == "📝 Отзывы")
async def show_reviews(message: Message):
    if await is_admin(message.from_user.id):
        if reviews:
            reviews_text = "\n\n".join([f"👤 {r['user']}: {r['text']}" for r in reviews])
            await message.answer(f"📝 Последние отзывы:\n\n{reviews_text}")
        else:
            await message.answer("😢 Отзывов пока нет")

# Обработка поддержки
@dp.message(F.text == "💬 Поддержка")
async def support_handler(message: Message, state: FSMContext):
    await state.set_state(States.waiting_question)
    await message.answer("Напишите ваш отзыв или вопрос:")

@dp.message(States.waiting_question)
async def save_review(message: Message, state: FSMContext):
    reviews.append({
        "user": message.from_user.username,
        "text": message.text,
        "date": datetime.now().strftime("%d.%m.%Y %H:%M")
    })
    await message.answer("✅ Ваше сообщение сохранено!")
    await state.clear()

# Покупка – вывод товаров
@dp.message(F.text == "🛒 Купить")
async def show_products(message: Message, state: FSMContext):
    try:
        if not products:
            return await message.answer("❌ Нет доступных товаров.")
        product_keys = list(products.keys())
        buttons = []
        for i in range(0, len(product_keys), 2):
            row = product_keys[i:i+2]
            buttons.append([KeyboardButton(text=item) for item in row])
        # Кнопка «↩ Назад» для возврата в главное меню
        buttons.append([KeyboardButton(text="↩ Назад")])
        
        kb = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
        await state.set_state(States.choosing_product)
        await message.answer("Выберите товар:", reply_markup=kb)
    except Exception as e:
        logger.error(f"Show products error: {e}")

@dp.message(States.choosing_product)
async def choose_product(message: Message, state: FSMContext):
    try:
        product = message.text
        # Если нажата кнопка «↩ Назад», возвращаем в главное меню
        if product == "↩ Назад":
            await go_back_main_menu(message, state)
            return
        
        if product not in products:
            return await message.answer("❌ Товар не найден")
        
        await state.update_data(product=product)
        await state.set_state(States.entering_player_id)
        await message.answer("🔢 Введите ваш игровой ID (цифры, от 7 до 15 символов):")
    except Exception as e:
        logger.error(f"Choose product error: {e}")

@dp.message(States.entering_player_id)
async def handle_player_id(message: Message, state: FSMContext):
    try:
        if message.text == "↩ Назад":
            await go_back_main_menu(message, state)
            return
        
        player_id = message.text.strip()
        if not player_id.isdigit() or not (7 <= len(player_id) <= 15):
            return await message.answer("❌ ID должен содержать только цифры и быть от 7 до 15 символов.")
        
        await state.update_data(player_id=player_id)
        await state.set_state(States.entering_promocode)
        
        # Отправляем сообщение с кнопкой "Нет промокода"
        inline_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Нет промокода", callback_data="no_promocode")]
        ])
        await message.answer("🎫 Введите промокод или нажмите кнопку, если его нет:", reply_markup=inline_kb)
    except Exception as e:
        logger.error(f"Player ID error: {e}")

@dp.message(States.entering_promocode)
async def handle_promocode(message: Message, state: FSMContext):
    try:
        if message.text == "↩ Назад":
            await go_back_main_menu(message, state)
            return
        
        promo = message.text.strip()
        if promo.upper() == "НЕТ ПРОМОКОДА":
            promo = "-"
        else:
            if not (promo.isalpha() and promo.isupper() and len(promo) == 6):
                return await message.answer("❌ Неверный формат промокода! Он должен состоять из 6 заглавных букв. Попробуйте еще раз или нажмите кнопку 'Нет промокода'.")
        
        data = await state.get_data()
        price = products[data["product"]]
        
        if promo != "-" and promo in promocodes:
            discount = promocodes[promo]
            price -= price * discount // 100
            await state.update_data(promocode=promo, discount=discount)
        else:
            promo = "-"
            await state.update_data(promocode=promo)
        
        await state.update_data(price=price)
        await state.set_state(States.waiting_payment)
        
        payment_text = (
            f"💸 Сумма к оплате: {price} сомони\n"
            f"📞 Реквизиты: +992 918 191451\n\n"
            f"📸 Отправьте фото чека\n\n"
            f"🎮 Ваш ID: {data.get('player_id', 'не указан')}"
        )
        await message.answer(payment_text)
    except Exception as e:
        logger.error(f"Promocode error: {e}")

@dp.callback_query(F.data == "no_promocode")
async def handle_no_promocode(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.delete_reply_markup()
        data = await state.get_data()
        price = products[data["product"]]
        await state.update_data(promocode="-", price=price)
        await state.set_state(States.waiting_payment)
        payment_text = (
            f"💸 Сумма к оплате: {price} сомони\n"
            f"📞 Реквизиты: +992 918 191451\n\n"
            f"📸 Отправьте фото чека\n\n"
            f"🎮 Ваш ID: {data.get('player_id', 'не указан')}"
        )
        await callback.message.answer(payment_text)
        await callback.answer()
    except Exception as e:
        logger.error(f"No promocode callback error: {e}")

@dp.message(States.waiting_payment, F.photo)
async def handle_payment(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        user = message.from_user
        pending_payments[user.id] = data
        statistics["total_orders"] += 1
        
        caption = (
            f"🧾 Новый заказ\n"
            f"👤: @{user.username}\n"
            f"🆔: {user.id}\n"
            f"🎮 ID: {data.get('player_id', 'не указан')}\n"
            f"📦 Товар: {data['product']}\n"
            f"💵 Сумма: {data['price']} сомони\n"
            f"🎫 Промокод: {data.get('promocode', 'не использован')}"
        )
        # Добавляем инлайн-клавиатуру для подтверждения выполнения заказа
        inline_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Выполнено", callback_data=f"order_done_{user.id}")]
        ])
        
        await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=caption, reply_markup=inline_kb)
        await message.answer("✅ Чек принят! Ожидайте подтверждения")
        await state.clear()
    except Exception as e:
        logger.error(f"Payment error: {e}")

# Универсальный обработчик «↩ Назад»
@dp.message(F.text == "↩ Назад")
async def go_back_main_menu(message: Message, state: FSMContext):
    await state.clear()
    kb = get_main_menu(message.from_user.id)
    await message.answer("Вы вернулись в главное меню:", reply_markup=kb)

# Обработчик нажатия кнопки "Выполнено" (админ)
@dp.callback_query(lambda c: c.data and c.data.startswith("order_done_"))
async def handle_order_done(callback: types.CallbackQuery, state: FSMContext):
    try:
        # Извлекаем id покупателя из callback_data вида "order_done_{user_id}"
        parts = callback.data.split("_")
        if len(parts) >= 3:
            buyer_id = int(parts[2])
        else:
            await callback.answer("Неверные данные заказа!", show_alert=True)
            return

        inline_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Получил товар", callback_data=f"order_received_{buyer_id}")]
        ])
        # Отправляем сообщение покупателю
        await bot.send_message(buyer_id, "Ваш заказ выполнен, проверяйте и подтверждайте получение", reply_markup=inline_kb)
        await callback.answer("Заказ отмечен как выполненный. Уведомление отправлено покупателю.", show_alert=True)
    except Exception as e:
        logger.error(f"Order done handler error: {e}")
        await callback.answer("Ошибка при обработке заказа.", show_alert=True)

# Обработчик нажатия кнопки "Получил товар" (покупатель)
@dp.callback_query(lambda c: c.data and c.data.startswith("order_received_"))
async def handle_order_received(callback: types.CallbackQuery):
    try:
        parts = callback.data.split("_")
        if len(parts) >= 3:
            buyer_id = int(parts[2])
        else:
            await callback.answer("Неверные данные заказа!", show_alert=True)
            return

        await bot.send_message(buyer_id, "Спасибо за подтверждение получения товара!")
        await callback.answer("Получение подтверждено", show_alert=True)
    except Exception as e:
        logger.error(f"Order received handler error: {e}")
        await callback.answer("Ошибка при подтверждении получения.", show_alert=True)

# Запуск бота
async def main():
    # Удаление старого webhook (если он был установлен)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())