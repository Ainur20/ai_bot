import telebot
import traceback
from functools import wraps
from telebot import types
from database import init_db, add_user, get_user, get_stats, logger, clear_history
from ai_engine import generate_response_with_history as generate_response
from config import BOT_TOKEN, ADMIN_IDS

bot = telebot.TeleBot(BOT_TOKEN)


@bot.message_handler(commands=['start'])
def send_welcome(message):
    # Преобразуем объект пользователя в словарь для add_user
    user_dict = {
        'id': message.from_user.id,
        'username': message.from_user.username,
        'first_name': message.from_user.first_name,
        'last_name': message.from_user.last_name,
        'language_code': message.from_user.language_code,
        'is_bot': message.from_user.is_bot
    }

    # Просто вызываем функцию — вся сложность спрятана в database.py
    add_user(user_dict)

    welcome_text = f"""
    Привет, {message.from_user.first_name}! 
    Теперь я знаю о тебе всё необходимое и запомнил это навсегда.
    """
    bot.reply_to(message, welcome_text)

# 5. Обработчик команды /help
@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = """
    Вот что я пока умею:
    /start - Поздороваться и начать работу
    /help - Показать это сообщение
    /profile - Ваш профиль
    /set_model - Для смены модели ИИ
    /set_temp - Для настройки креативности
    /clear_history - Забыть всю историю диалога
    """
    bot.reply_to(message, help_text)

# Декоратор для обработки ошибок во всех хендлерах
def handle_errors(func):
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        try:
            return func(message, *args, **kwargs)
        except KeyError as e:
            logger.error(f"KeyError в {func.__name__}: {e}\n{traceback.format_exc()}")
            bot.reply_to(message, "⚠️ Ошибка в данных. Попробуйте позже или напишите /start")
        except Exception as e:
            logger.error(f"Ошибка в {func.__name__}: {e}\n{traceback.format_exc()}")
            bot.reply_to(message, "❌ Произошла внутренняя ошибка. Разработчик уведомлен.")

    return wrapper


@bot.message_handler(commands=['profile'])
@handle_errors
def show_profile(message):
    user_data = get_user(message.from_user.id)

    if not user_data:
        bot.reply_to(message, "Кажется, мы не знакомы. Напиши /start.")
        return

    # Безопасный доступ к данным - показываем ВСЕ поля
    profile_text = f"""
    👤<b>Твой профиль:</b>
    ID: `{user_data.get('user_id', 'N/A')}`
    Username: @{user_data.get('username', 'отсутствует')}
    Имя: {user_data.get('first_name') or 'Не указано'}
    Фамилия: {user_data.get('last_name') or 'Не указано'}
    Язык: {user_data.get('language_code') or 'не определён'}
    Бот: {'Да' if user_data.get('is_bot') else 'Нет'}
    
    📅<b>Даты:</b>
    Зарегистрирован: {user_data.get('created_at', 'неизвестно')[:10]}
    Последний визит: {user_data.get('last_seen', 'неизвестно')[:19]}
    
    ⚙️<b>Настройки ИИ:</b>
    Модель: `{user_data.get('ai_model', 'не настроена')}`
    Креативность: {user_data.get('temperature', 'не настроена')}"""

    bot.reply_to(message, profile_text, parse_mode='html')


@bot.message_handler(commands=['stats'])
def show_stats(message):
    # Простая проверка на админа (подставьте свой Telegram ID)
    if message.from_user.id not in ADMIN_IDS:  # Замените на ваш ID
        bot.reply_to(message, "Эта команда только для разработчика.")
        return

    stats = get_stats()
    if stats:
        stats_text = f"""
        📈 Статистика бота:
        Всего пользователей: {stats['total_users']}
        Активных сегодня: {stats['active_today']}
        С настройками ИИ: {stats['users_with_settings']}
        """
        bot.reply_to(message, stats_text, parse_mode='html')
    else:
        bot.reply_to(message, "Не удалось получить статистику.")

@bot.message_handler(commands=['set_model'])
@handle_errors
def set_model_command(message):
    """Команда для смены модели ИИ."""
    user_data = get_user(message.from_user.id)
    if not user_data:
        bot.reply_to(message, "Сначала напиши /start")
        return

    # Простейший парсинг аргументов команды
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message,
                     "Использование: /set_model <название_модели>\n"
                     "Например: /set_model deepseek/deepseek-r1-0528:free\n"
                     "Или: /set_model arcee-ai/trinity-mini:free"
                     )
        return

    new_model = args[1]

    # Обновляем настройки в базе
    from database import update_user_settings
    if update_user_settings(message.from_user.id, {'ai_model': new_model}):
        bot.reply_to(message, f"✅ Модель изменена на: {new_model}")
    else:
        bot.reply_to(message, "❌ Не удалось изменить модель.")


@bot.message_handler(commands=['set_temp'])
@handle_errors
def set_temp_command(message):
    """Команда для настройки креативности (temperature)."""
    user_data = get_user(message.from_user.id)
    if not user_data:
        bot.reply_to(message, "Сначала напиши /start")
        return

    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message,
                     "Использование: /set_temp <число от 0.0 до 1.0>\n"
                     "0.0 — строгие ответы, 1.0 — баланс."
                     )
        return

    try:
        new_temp = float(args[1])
        if not 0.0 <= new_temp <= 1.0:
            raise ValueError

        from database import update_user_settings
        if update_user_settings(message.from_user.id, {'temperature': new_temp}):
            bot.reply_to(message, f"✅ Креативность установлена: {new_temp}")
        else:
            bot.reply_to(message, "❌ Не удалось изменить настройку.")
    except ValueError:
        bot.reply_to(message, "❌ Введите число от 0.0 до 1.0")

@bot.message_handler(commands=['clear_history'])
@handle_errors
def clear_history_command(message):
    """Команда для очистки истории диалога с подтверждением."""
    user_data = get_user(message.from_user.id)
    if not user_data:
        bot.reply_to(message, "Сначала напиши /start")
        return

    # Создаём клавиатуру с кнопками
    keyboard = types.InlineKeyboardMarkup()
    yes_button = types.InlineKeyboardButton("Да, очистить", callback_data="confirm_clear_history")
    no_button = types.InlineKeyboardButton("Нет, отмена", callback_data="cancel_clear_history")
    keyboard.add(yes_button, no_button)

    bot.reply_to(
        message,
        "⚠️ Вы уверены, что хотите очистить историю диалога?\n"
        "Это действие нельзя отменить. Все сообщения будут удалены.",
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data in ["confirm_clear_history", "cancel_clear_history"])
@handle_errors
def handle_clear_history_confirmation(call):
    """Обработка подтверждения очистки истории."""
    if call.data == "confirm_clear_history":
        if clear_history(call.from_user.id):
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="✅ История диалога очищена. Начинаем с чистого листа!"
            )
        else:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="❌ Не удалось очистить историю."
            )
    else:  # cancel_clear_history
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="🧹 Очистка отменена. История сохранена."
        )

    # Подтверждаем нажатие кнопки (убираем "часики" в Telegram)
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    # Показываем статус "печатает"
    bot.send_chat_action(message.chat.id, 'typing')

    # Генерируем ответ
    response_text = generate_response(message.from_user.id, message.text)

    if response_text is None:
        # Пользователь не найден в базе
        bot.reply_to(
            message,
            "Кажется, мы ещё не знакомы. Давай начнём с команды /start"
        )
    else:
        # Отправляем сгенерированный ответ
        bot.reply_to(message, response_text, parse_mode="Markdown")


# Инициализируем базу данных при запуске
if not init_db():
    print("❌ Не удалось инициализировать базу данных. Бот не может работать.")
    exit(1)

if __name__ == "__main__":
    print("🤖 Бот запускается...")
    bot.infinity_polling(none_stop=True)
