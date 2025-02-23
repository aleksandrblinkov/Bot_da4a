import telebot
from telebot import types
import os
import psycopg2
import time
from collections import defaultdict
import logging

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получение токена бота
YOUR_BOT_TOKEN = os.environ.get('YOUR_BOT_TOKEN')

# Если переменная окружения не установлена, используйте токен напрямую (только для локальной разработки)
if not YOUR_BOT_TOKEN:
    YOUR_BOT_TOKEN = "5679093544:AAEZgFeVu-lgPM00oP1kfaUduCJlpR2_Uug"  # Замените на ваш токен
    logger.warning("Переменная окружения YOUR_BOT_TOKEN не установлена. Используется токен из кода.")

# Инициализация бота
bot = telebot.TeleBot(YOUR_BOT_TOKEN)

# Подключение к PostgreSQL
def get_db_connection():
    DATABASE_URL = os.environ.get('DATABASE_URL')
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    return conn

# Создание таблиц
def create_tables():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS quizzes (
        id SERIAL PRIMARY KEY,
        name VARCHAR NOT NULL,
        admin_id INT NOT NULL
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS questions (
        id SERIAL PRIMARY KEY,
        quiz_id INT NOT NULL,
        question VARCHAR NOT NULL,
        answer VARCHAR NOT NULL,
        photo VARCHAR,
        FOREIGN KEY (quiz_id) REFERENCES quizzes (id) ON DELETE CASCADE
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS results (
        id SERIAL PRIMARY KEY,
        quiz_id INT NOT NULL,
        user_id INT NOT NULL,
        username VARCHAR NOT NULL,
        score INT DEFAULT 0,
        FOREIGN KEY (quiz_id) REFERENCES quizzes (id) ON DELETE CASCADE
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admins (
        id SERIAL PRIMARY KEY,
        user_id INT NOT NULL,
        username VARCHAR NOT NULL
    )
    ''')
    conn.commit()
    conn.close()

# Инициализация администратора
def initialize_admin():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Твой ID и username
    admin_id = 881514562
    admin_username = "mangata_al"

    # Проверяем, есть ли ты в таблице admins
    cursor.execute("SELECT user_id FROM admins WHERE user_id = %s", (admin_id,))
    result = cursor.fetchone()

    # Если тебя нет, добавляем
    if not result:
        cursor.execute("INSERT INTO admins (user_id, username) VALUES (%s, %s)", (admin_id, admin_username))
        conn.commit()
        logger.info(f"Администратор @{admin_username} (ID: {admin_id}) добавлен в базу данных.")

    conn.close()

# Создаем таблицы и добавляем администратора
create_tables()
initialize_admin()

# Временные данные для создания викторин
temp_data = {}

# Текущие активные викторины
active_quizzes = defaultdict(dict)

# Команда /start
@bot.message_handler(commands=['start'])
def start_command(message):
    bot.send_message(message.chat.id, "Привет! Я бот для викторин. Используй /help чтобы увидеть список команд.")

@bot.message_handler(commands=['clear_keyboard'])
def clear_keyboard(message):
# Удаляем клавиатуру у всех пользователей
    markup = types.ReplyKeyboardRemove(selective=False)
    bot.send_message(message.chat.id, "Клавиатура очищена.", reply_markup=markup)

# Проверка, является ли пользователь админом
def is_admin(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM admins WHERE user_id = %s", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

# Команда /help
@bot.message_handler(commands=['help'])
def help_command(message):
    if is_admin(message.from_user.id):
        commands = """
📜 Список команд для админов:
/add_quiz - Добавить новую викторину
/delete_quiz - Удалить викторину
/start_quiz - Запустить викторину в общем чате
/admin_commands - Показать все команды для админов
/help - Показать список команд
"""
    else:
        commands = """
📜 Список команд для пользователей:
/start_quiz - Запустить викторину
/help - Показать список команд
"""
    bot.send_message(message.chat.id, commands)

# Команда /admin_commands
@bot.message_handler(commands=['admin_commands'])
def admin_commands(message):
    if is_admin(message.from_user.id):
        commands = """
🎮 Команды для админов:
/add_quiz - Добавить новую викторину
/delete_quiz - Удалить викторину
/start_quiz - Запустить викторину в общем чате
/add_admin - Добавить нового админа
/remove_admin - Удалить админа
/admin_commands - Показать все команды для админов
"""
        bot.send_message(message.chat.id, commands)
    else:
        bot.send_message(message.chat.id, "У вас нет прав для выполнения этой команды.")

# Добавление админа
@bot.message_handler(commands=['add_admin'])
def add_admin(message):
    if is_admin(message.from_user.id):
        msg = bot.send_message(message.chat.id, "Перешлите любое сообщение от пользователя, которого нужно сделать админом.")
        bot.register_next_step_handler(msg, process_add_admin)
    else:
        bot.send_message(message.chat.id, "❌ У вас нет прав для выполнения этой команды.")

def process_add_admin(message):
    if not (message.forward_from or message.forward_from_chat):
        bot.send_message(message.chat.id, "❌ Это не пересланное сообщение. Пожалуйста, перешлите сообщение от пользователя.")
        return

    if message.forward_from:
        user_id = message.forward_from.id
        username = message.forward_from.username or message.forward_from.first_name
    else:
        bot.send_message(message.chat.id, "❌ Нельзя добавить админа из группы или канала. Перешлите сообщение из личного чата.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT user_id FROM admins WHERE user_id = %s", (user_id,))
        if cursor.fetchone():
            bot.send_message(message.chat.id, f"❌ Пользователь @{username} уже является админом.")
            return

        cursor.execute("INSERT INTO admins (user_id, username) VALUES (%s, %s)", (user_id, username))
        conn.commit()
        bot.send_message(message.chat.id, f"✅ Пользователь @{username} успешно добавлен в список админов!")
    except Exception as e:
        logger.error(f"Ошибка при добавлении админа: {e}")
        bot.send_message(message.chat.id, "❌ Произошла ошибка при добавлении админа.")
    finally:
        conn.close()

# Удаление админа
@bot.message_handler(commands=['remove_admin'])
def remove_admin(message):
    if is_admin(message.from_user.id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM admins")
        admins = cursor.fetchall()
        conn.close()
        if not admins:
            bot.send_message(message.chat.id, "Нет доступных админов для удаления.")
            return

        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
        for admin in admins:
            markup.add(f"@{admin[0]}")
        msg = bot.send_message(message.chat.id, "Выберите админа для удаления:", reply_markup=markup)
        bot.register_next_step_handler(msg, process_remove_admin)

def process_remove_admin(message):
    username = message.text.strip("@")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM admins WHERE username = %s", (username,))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, f"Админ @{username} удален.")

# Добавление викторины
@bot.message_handler(commands=['add_quiz'])
def add_quiz(message):
    if is_admin(message.from_user.id):
        msg = bot.send_message(message.chat.id, "Введите название викторины:")
        bot.register_next_step_handler(msg, process_quiz_name)
    else:
        bot.send_message(message.chat.id, "У вас нет прав для выполнения этой команды.")

def process_quiz_name(message):
    quiz_name = message.text
    temp_data[message.from_user.id] = {'quiz_name': quiz_name, 'questions': []}
    msg = bot.send_message(message.chat.id, f"Викторина '{quiz_name}' создана. Теперь добавьте вопросы. Введите первый вопрос:")
    bot.register_next_step_handler(msg, process_question)

def process_question(message):
    question = message.text
    temp_data[message.from_user.id]['questions'].append({'question': question, 'answer': None, 'photo': None})
    msg = bot.send_message(message.chat.id, "Введите ответ на этот вопрос:")
    bot.register_next_step_handler(msg, process_answer)

def process_answer(message):
    answer = message.text
    user_id = message.from_user.id
    temp_data[user_id]['questions'][-1]['answer'] = answer
    msg = bot.send_message(message.chat.id, "Хотите добавить фото к вопросу? (Отправьте фото или напишите 'нет')")
    bot.register_next_step_handler(msg, process_photo)

def process_photo(message):
    user_id = message.from_user.id
    if message.photo:
        photo_id = message.photo[-1].file_id
        temp_data[user_id]['questions'][-1]['photo'] = photo_id
    else:
        temp_data[user_id]['questions'][-1]['photo'] = None

    question_data = temp_data[user_id]['questions'][-1]
    preview = f"📝 Вопрос: {question_data['question']}\n✅ Ответ: {question_data['answer']}"
    if question_data['photo']:
        bot.send_photo(message.chat.id, question_data['photo'], caption=preview)
    else:
        bot.send_message(message.chat.id, preview)

    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
    markup.add("Добавить еще вопрос", "Завершить викторину")
    msg = bot.send_message(message.chat.id, "Что дальше?", reply_markup=markup)
    bot.register_next_step_handler(msg, handle_quiz_creation)

def handle_quiz_creation(message):
    user_id = message.from_user.id
    if message.text == "Добавить еще вопрос":
        msg = bot.send_message(message.chat.id, "Введите следующий вопрос:")
        bot.register_next_step_handler(msg, process_question)
    else:
        quiz_name = temp_data[user_id]['quiz_name']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO quizzes (name, admin_id) VALUES (%s, %s) RETURNING id", (quiz_name, user_id))
        quiz_id = cursor.fetchone()[0]

        for question in temp_data[user_id]['questions']:
            cursor.execute("INSERT INTO questions (quiz_id, question, answer, photo) VALUES (%s, %s, %s, %s)",
                           (quiz_id, question['question'], question['answer'], question['photo']))

        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"Викторина '{quiz_name}' успешно сохранена!")
        del temp_data[user_id]

# Удаление викторины
@bot.message_handler(commands=['delete_quiz'])
def delete_quiz(message):
    # Проверяем, является ли пользователь админом
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ У вас нет прав для удаления викторины. Обратитесь к админу.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM quizzes")
    quizzes = cursor.fetchall()
    conn.close()

    if not quizzes:
        bot.send_message(message.chat.id, "Нет доступных викторин для удаления.")
        return

    # Создаем inline-клавиатуру с выбором викторин для удаления
    markup = types.InlineKeyboardMarkup()
    for quiz in quizzes:
        markup.add(types.InlineKeyboardButton(
            text=f"{quiz[1]} (ID: {quiz[0]})",  # Название и ID викторины
            callback_data=f"delete_quiz_{quiz[0]}"  # Данные для обработки (ID викторины)
        ))

    # Отправляем сообщение с inline-клавиатурой
    bot.send_message(message.chat.id, "Выберите викторину для удаления:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_quiz_"))
def process_delete_quiz(call):
    # Проверяем, является ли пользователь админом
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ У вас нет прав для удаления викторины.")
        return

    # Извлекаем ID викторины из callback_data
    quiz_id = int(call.data.split("_")[2])

    # Получаем название викторины из базы данных
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM quizzes WHERE id = %s", (quiz_id,))
    quiz_name = cursor.fetchone()[0]

    try:
        # Удаляем викторину и связанные вопросы (благодаря ON DELETE CASCADE)
        cursor.execute("DELETE FROM quizzes WHERE id = %s", (quiz_id,))
        conn.commit()
        bot.answer_callback_query(call.id, f"Викторина '{quiz_name}' удалена.")
        bot.send_message(call.message.chat.id, f"✅ Викторина '{quiz_name}' успешно удалена.")
    except Exception as e:
        logger.error(f"Ошибка при удалении викторины: {e}")
        bot.answer_callback_query(call.id, "❌ Произошла ошибка при удалении викторины.")
    finally:
        conn.close()


# Запуск викторины в общем чате
@bot.message_handler(commands=['start_quiz'])
def start_quiz(message):
    # Проверяем, является ли пользователь админом
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ У вас нет прав для запуска викторины. Обратитесь к админу.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM quizzes")
    quizzes = cursor.fetchall()
    conn.close()

    if not quizzes:
        bot.send_message(message.chat.id, "Нет доступных викторин.")
        return

    # Создаем inline-клавиатуру с выбором викторин
    markup = types.InlineKeyboardMarkup()
    for quiz in quizzes:
        # Добавляем кнопку для каждой викторины
        markup.add(types.InlineKeyboardButton(
            text=quiz[1],  # Название викторины
            callback_data=f"start_quiz_{quiz[0]}"  # Данные для обработки (ID викторины)
        ))

    # Отправляем сообщение с inline-клавиатурой
    bot.send_message(message.chat.id, "Выберите викторину для запуска:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("start_quiz_"))
def process_start_quiz(call):
    # Проверяем, является ли пользователь админом
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ У вас нет прав для запуска викторины.")
        return

    # Извлекаем ID викторины из callback_data
    quiz_id = int(call.data.split("_")[2])

    # Получаем название викторины из базы данных
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM quizzes WHERE id = %s", (quiz_id,))
    quiz_name = cursor.fetchone()[0]
    conn.close()

    # Инициализируем викторину
    active_quizzes[call.message.chat.id] = {
        'quiz_id': quiz_id,
        'current_question': 0,
        'scores': defaultdict(int),
        'current_answer': None  # Добавляем ключ 'current_answer'
    }

    # Уведомляем администратора о начале викторины
    bot.send_message(call.message.chat.id, f"🎉 Викторина '{quiz_name}' начнется через 15 секунд! Приготовьтесь!")
    time.sleep(15)
    ask_question(call.message.chat.id, quiz_id)

def ask_question(chat_id, quiz_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT question, answer, photo FROM questions WHERE quiz_id = %s", (quiz_id,))
    questions = cursor.fetchall()
    conn.close()

    if not questions:
        bot.send_message(chat_id, "В этой викторине нет вопросов.")
        end_quiz(chat_id, quiz_id)
        return

    current_question = active_quizzes[chat_id]['current_question']
    if current_question >= len(questions):
        end_quiz(chat_id, quiz_id)
        return

    question, answer, photo = questions[current_question]
    active_quizzes[chat_id]['current_answer'] = answer.lower()  # Добавляем ключ 'current_answer'

    if photo:
        bot.send_photo(chat_id, photo, caption=f"❓ Вопрос: {question}")
    else:
        bot.send_message(chat_id, f"❓ Вопрос: {question}")


# Обработка ответов
@bot.message_handler(func=lambda message: message.chat.id in active_quizzes)
def handle_answer(message):
    chat_id = message.chat.id

    # Проверяем, активна ли викторина и есть ли текущий вопрос
    if chat_id not in active_quizzes or 'current_answer' not in active_quizzes[chat_id]:
        bot.send_message(chat_id, "❌ Викторина не активна или вопрос не задан.")
        return

    user_answer = message.text.lower()
    correct_answer = active_quizzes[chat_id]['current_answer']

    if user_answer == correct_answer:
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name
        active_quizzes[chat_id]['scores'][user_id] += 1
        bot.send_message(chat_id, f"🎉 Правильно! @{username} получает очко!")

        show_scores(chat_id)

        # Переходим к следующему вопросу
        active_quizzes[chat_id]['current_question'] += 1
        time.sleep(5)
        ask_question(chat_id, active_quizzes[chat_id]['quiz_id'])


def show_scores(chat_id):
    scores = active_quizzes[chat_id]['scores']
    if not scores:
        return

    scoreboard = "🏆 Текущие результаты:\n"
    for user_id, score in scores.items():
        user = bot.get_chat_member(chat_id, user_id).user
        username = user.username or user.first_name
        scoreboard += f"👤 @{username}: {score} очков\n"
    bot.send_message(chat_id, scoreboard)

def end_quiz(chat_id, quiz_id):
    scores = active_quizzes[chat_id]['scores']
    if not scores:
        bot.send_message(chat_id, "Викторина завершена, но никто не ответил правильно.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    for user_id, score in scores.items():
        user = bot.get_chat_member(chat_id, user_id).user
        username = user.username or user.first_name
        cursor.execute("INSERT INTO results (quiz_id, user_id, username, score) VALUES (%s, %s, %s, %s)",
                       (quiz_id, user_id, username, score))
    conn.commit()
    conn.close()

    final_scoreboard = "🏆 Финальные результаты:\n"
    for user_id, score in scores.items():
        user = bot.get_chat_member(chat_id, user_id).user
        username = user.username or user.first_name
        final_scoreboard += f"👤 @{username}: {score} очков\n"
    bot.send_message(chat_id, final_scoreboard)
    bot.send_message(chat_id, "🎉 Викторина завершена! Спасибо за участие!")

    del active_quizzes[chat_id]

# Обработка ошибок
@bot.message_handler(func=lambda message: True)
def handle_errors(message):
    try:
        bot.process_new_messages([message])
    except Exception as ex:
        logger.error(f"Ошибка: {ex}", exc_info=True)
        bot.send_message(message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте еще раз.")

# Запуск бота
if __name__ == '__main__':
    logger.info("Бот запущен и работает...")
    bot.polling(none_stop=True)
