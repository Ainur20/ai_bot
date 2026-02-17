# database.py
import sqlite3
import logging


# Настраиваем логирование, чтобы видеть ошибки в консоли
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Имя файла базы данных — вынесем в константу, чтобы легко менять
DB_NAME = 'my_bot_database.db'


def get_connection():
    """Создаёт и возвращает соединение с базой данных"""
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logger.error(f"Не удалось подключиться к базе данных: {e}")
        return None

def init_db():
    """Инициализирует базу данных, создаёт таблицы, если их нет."""
    conn = get_connection()
    if conn is None:
        return False

    try:
        cursor = conn.cursor()
        # Таблица users
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                language_code TEXT,
                is_bot INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # А вот представьте, что завтра нам понадобится таблица для заказов
        # Мы можем добавить её здесь, и она создастся автоматически
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                ai_model TEXT DEFAULT 'arcee-ai/trinity-large-preview:free',
                temperature REAL DEFAULT 0.7,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS message_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,  -- 'user' или 'assistant'
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
            )
        ''')

        conn.commit()
        logger.info("База данных инициализирована, таблицы готовы.")
        return True
    except sqlite3.Error as e:
        logger.error(f"Ошибка при создании таблиц: {e}")
        return False
    finally:
        if conn:
            conn.close()


def add_user(user_data):
    """Добавляет нового пользователя в базу или обновляет информацию о существующем."""
    # user_data — это словарь с полями из объекта message.from_user
    conn = get_connection()
    if conn is None:
        return False

    try:
        cursor = conn.cursor()
        # Вставка с обновлением данных при конфликте (ON CONFLICT DO UPDATE SET)
        cursor.execute('''
            INSERT INTO users (user_id, username, first_name, last_name, language_code, is_bot, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                language_code = excluded.language_code,
                last_seen = CURRENT_TIMESTAMP
        ''', (
            user_data.get('id'),
            user_data.get('username'),
            user_data.get('first_name'),
            user_data.get('last_name'),
            user_data.get('language_code'),
            1 if user_data.get('is_bot') else 0
        ))

        conn.commit()

        # Сразу создаём запись в настройках по умолчанию для нового пользователя
        cursor.execute('''
            INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)
        ''', (user_data.get('id'),))
        conn.commit()

        logger.info(f"Пользователь {user_data.get('id')} добавлен/обновлён в базе.")
        return True
    except sqlite3.Error as e:
        logger.error(f"Ошибка при добавлении пользователя {user_data.get('id')}: {e}")
        return False
    finally:
        if conn:
            conn.close()


def get_user(user_id):
    """Возвращает данные пользователя по его Telegram ID."""
    conn = get_connection()
    if conn is None:
        return None

    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT u.*, us.ai_model, us.temperature 
            FROM users u
            LEFT JOIN user_settings us ON u.user_id = us.user_id
            WHERE u.user_id = ?
        ''', (user_id,))

        row = cursor.fetchone()
        if row:
            # Преобразуем строку Row в словарь для удобства
            return dict(row)
        return None
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении пользователя {user_id}: {e}")
        return None
    finally:
        if conn:
            conn.close()


def get_stats():
    """Возвращает статистику по базе данных."""
    conn = get_connection()
    if conn is None:
        return None

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total_users FROM users")
        total_users = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) as active_today FROM users WHERE date(last_seen) = date('now')")
        active_today = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) as users_with_settings FROM user_settings")
        users_with_settings = cursor.fetchone()[0]

        return {
            'total_users': total_users,
            'active_today': active_today,
            'users_with_settings': users_with_settings
        }
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении статистики: {e}")
        return None
    finally:
        if conn:
            conn.close()


def add_to_history(user_id, role, content):
    """Добавляет сообщение в историю диалога пользователя."""
    conn = get_connection()
    if conn is None:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO message_history (user_id, role, content) VALUES (?, ?, ?)",
            (user_id, role, content)
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Ошибка при добавлении в историю: {e}")
        return False
    finally:
        if conn:
            conn.close()

def clear_history(user_id):
    """Удаляет всю историю диалога пользователя."""
    conn = get_connection()
    if conn is None:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM message_history WHERE user_id = ?", (user_id,))
        conn.commit()
        logger.info(f"История пользователя {user_id} очищена.")
        return True
    except sqlite3.Error as e:
        logger.error(f"Ошибка при очистке истории {user_id}: {e}")
        return False
    finally:
        if conn:
            conn.close()
def get_recent_history(user_id, limit=10):
    """Возвращает последние N сообщений из истории диалога пользователя."""
    conn = get_connection()
    if conn is None:
        return []

    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT role, content 
            FROM message_history 
            WHERE user_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (user_id, limit))

        # Возвращаем в прямом порядке (от старых к новым)
        rows = cursor.fetchall()
        return [{"role": row[0], "content": row[1]} for row in reversed(rows)]
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении истории: {e}")
        return []
    finally:
        if conn:
            conn.close()


def update_user_settings(user_id, updates):
    """Обновляет настройки ИИ пользователя."""
    if not updates:
        return False

    ALLOWED_SETTINGS = {'ai_model', 'temperature'}
    filtered_updates = {k: v for k, v in updates.items() if k in ALLOWED_SETTINGS}

    if not filtered_updates:
        logger.warning(f"Попытка обновления недопустимых настроек: {list(updates.keys())}")
        return False

    conn = get_connection()
    if conn is None:
        return False

    try:
        cursor = conn.cursor()

        # Имена колонок
        columns = ', '.join(filtered_updates.keys())
        # Значения для INSERT: сначала user_id, потом новые значения
        insert_values = [user_id] + list(filtered_updates.values())
        # Значения для UPDATE: только новые значения (столько же, сколько колонок)
        update_values = list(filtered_updates.values())

        # Формируем SET часть
        set_clause = ', '.join([f"{key} = ?" for key in filtered_updates.keys()])

        # Общий список значений: сначала для INSERT, потом для UPDATE
        all_values = insert_values + update_values

        query = f'''
            INSERT INTO user_settings (user_id, {columns})
            VALUES ({', '.join(['?'] * (1 + len(filtered_updates)))})
            ON CONFLICT(user_id) DO UPDATE SET {set_clause}
        '''

        cursor.execute(query, all_values)
        conn.commit()
        logger.info(f"Настройки пользователя {user_id} обновлены: {filtered_updates}")
        return True
    except sqlite3.Error as e:
        logger.error(f"Ошибка при обновлении настроек {user_id}: {e}")
        return False
    finally:
        if conn:
            conn.close()
