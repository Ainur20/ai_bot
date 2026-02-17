# ai_engine.py
import requests
import json
import logging
from typing import Optional
from database import get_user, get_recent_history
from config import OPENROUTER_API_KEY

logger = logging.getLogger(__name__)


def generate_response(user_id: int, user_message: str) -> Optional[str]:
    """
    Генерирует ответ на сообщение пользователя.

    Шаги:
    1. Получаем данные пользователя из БД
    2. Если пользователя нет — просим его представиться
    3. Если есть — берём его настройки ИИ
    4. Формируем промпт с учётом личности пользователя
    5. Отправляем запрос к OpenRouter
    6. Возвращаем ответ
    """

    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY не задан!")
        return "Ошибка конфигурации: API-ключ не настроен."

    # Шаг 1: Достаём пользователя из базы
    user_data = get_user(user_id)

    if not user_data:
        # Пользователь не найден в базе
        return None

    # Шаг 2: Готовим настройки для ИИ
    # Берём модель и температуру из настроек пользователя
    ai_model = user_data.get('ai_model', 'arcee-ai/trinity-large-preview:free')
    temperature = user_data.get('temperature', 0.7)

    # Шаг 3: Формируем системный промпт
    # Это инструкция для нейросети, которая задаёт её личность
    system_prompt = f"""Ты — помощник в Telegram. 
    Имя: {user_data.get('first_name', 'друг')}. 
    Язык: {user_data.get('language_code', 'ru')}.
    Отвечай кратко, по делу, на языке пользователя.
    Если список длинный, сократи его до 4 пунктов. Заверши предложение полностью."""

    # Шаг 4: Отправляем запрос к OpenRouter
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://your-course-site.com",
                "X-Title": "PRO Telegram Bots Course"
            },
            json={
                "model": ai_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                "temperature": temperature,
                "max_tokens": 1000
            },
            timeout=30
        )

        response.raise_for_status()
        result = response.json()

        # Достаём текст ответа из JSON
        ai_reply = result['choices'][0]['message']['content']

        return ai_reply

    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе к OpenRouter: {e}")
        return "Извини, у меня проблемы с подключением к нейросети. Попробуй позже."
    except (KeyError, json.JSONDecodeError) as e:
        logger.error(f"Ошибка парсинга ответа OpenRouter: {e}")
        return "Нейросеть ответила в странном формате. Попробуй задать вопрос иначе."


def generate_response_with_history(user_id: int, user_message: str) -> Optional[str]:
    """
    Генерирует ответ с учётом истории диалога.
    """
    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY не задан!")
        return "Ошибка конфигурации: API-ключ не настроен."

    user_data = get_user(user_id)
    if not user_data:
        return None

    # 1. Получаем историю БЕЗ текущего сообщения
    history = get_recent_history(user_id, limit=8)

    # 2. Формируем системный промпт
    system_prompt = f"""Ты — Telegram-бот. 
Имя пользователя: {user_data.get('first_name', 'друг')}.
Язык: {user_data.get('language_code', 'русский')}.

Отвечай на языке пользователя и учитывай контекст предыдущих сообщений."""

    # 3. Собираем контекст: system + история + новое сообщение
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)  # история уже в правильном порядке
    messages.append({"role": "user", "content": user_message})  # добавляем ТОЛЬКО один раз

    # 4. Отправляем запрос к OpenRouter
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://your-course-site.com",
                "X-Title": "PRO Telegram Bots Course"
            },
            json={
                "model": user_data.get('ai_model', 'arcee-ai/trinity-large-preview:free'),
                "messages": messages,
                "temperature": user_data.get('temperature', 0.7),
                "max_tokens": 1000
            },
            timeout=30
        )

        response.raise_for_status()
        result = response.json()
        ai_reply = result['choices'][0]['message']['content']

        # 5. Сохраняем ВЕСЬ диалог: сначала вопрос, потом ответ
        from database import add_to_history
        add_to_history(user_id, "user", user_message)
        add_to_history(user_id, "assistant", ai_reply)

        return ai_reply

    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка сети при запросе к OpenRouter: {e}")
        return "Извини, у меня проблемы с подключением к нейросети. Попробуй позже."
    except (KeyError, json.JSONDecodeError) as e:
        logger.error(f"Ошибка парсинга ответа OpenRouter: {e}")
        return "Нейросеть ответила в странном формате. Попробуй задать вопрос иначе."
