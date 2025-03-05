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
    try:
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
            user_id INT NOT NULL UNIQUE,
            username VARCHAR NOT NULL
        )
        ''')
        conn.commit()
        logger.info("Таблицы созданы или уже существуют.")
    except Exception as e:
        logger.error(f"Ошибка при создании таблиц: {e}")
    finally:
        conn.close()

# Инициализация администратора
def initialize_admin():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Ваш реальный ID и username
    admin_id = 881514562  # Замените на ваш реальный ID
    admin_username = "mangata_al"  # Замените на ваш username

    try:
        # Проверяем, есть ли вы в таблице admins
        cursor.execute("SELECT user_id FROM admins WHERE user_id = %s", (admin_id,))
        result = cursor.fetchone()

        # Если вас нет, добавляем
        if not result:
            cursor.execute("INSERT INTO admins (user_id, username) VALUES (%s, %s)", (admin_id, admin_username))
            conn.commit()
            logger.info(f"Администратор @{admin_username} (ID: {admin_id}) добавлен в базу данных.")
        else:
            logger.info(f"Администратор @{admin_username} (ID: {admin_id}) уже существует в базе данных.")
    except Exception as e:
        logger.error(f"Ошибка при добавлении администратора: {e}")
    finally:
        conn.close()

# Создаем таблицы и добавляем администратора
create_tables()
initialize_admin()

# Глобальные переменные
temp_data = {}  # Временные данные для создания викторин
active_quizzes = defaultdict(dict)  # Текущие активные викторины

# Проверка, является ли пользователь админом
def is_admin(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT user_id FROM admins WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()
        if result:
            logger.info(f"Пользователь {user_id} является администратором.")
            return True
        else:
            logger.info(f"Пользователь {user_id} не является администратором.")
            return False
    except Exception as e:
        logger.error(f"Ошибка при проверке администратора: {e}")
        return False
    finally:
        conn.close()

# Команда /start
@bot.message_handler(commands=['start'])
def start_command(message):
    if message.chat.type == "private":  # Если это личный чат с ботом
        markup = types.InlineKeyboardMarkup()
        if is_admin(message.from_user.id):
            markup.add(types.InlineKeyboardButton(text="Создать викторину", callback_data="create_quiz"))
            markup.add(types.InlineKeyboardButton(text="Запустить викторину", callback_data="start_quiz"))
            markup.add(types.InlineKeyboardButton(text="Редактировать викторину", callback_data="edit_quiz"))
            markup.add(types.InlineKeyboardButton(text="Удалить викторину", callback_data="delete_quiz"))
            markup.add(types.InlineKeyboardButton(text="Добавить админа", callback_data="add_admin"))
            markup.add(types.InlineKeyboardButton(text="Удалить админа", callback_data="remove_admin"))
        else:
            markup.add(types.InlineKeyboardButton(text="Запустить викторину", callback_data="start_quiz"))
        markup.add(types.InlineKeyboardButton(text="Помощь", callback_data="help"))
        bot.send_message(message.chat.id, "Привет! Я бот для викторин. Выберите действие:", reply_markup=markup)
    else:  # Если это общий чат
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text="Запустить викторину", callback_data="start_quiz"))
        bot.send_message(message.chat.id, "Привет! Я бот для викторин. Нажмите кнопку ниже, чтобы запустить викторину.", reply_markup=markup)

# Команда /help
@bot.callback_query_handler(func=lambda call: call.data == "help")
def help_command(call):
    markup = types.InlineKeyboardMarkup()
    if is_admin(call.from_user.id):
        markup.add(types.InlineKeyboardButton(text="Создать викторину", callback_data="create_quiz"))
        markup.add(types.InlineKeyboardButton(text="Запустить викторину", callback_data="start_quiz"))
        markup.add(types.InlineKeyboardButton(text="Редактировать викторину", callback_data="edit_quiz"))
        markup.add(types.InlineKeyboardButton(text="Удалить викторину", callback_data="delete_quiz"))
        markup.add(types.InlineKeyboardButton(text="Добавить админа", callback_data="add_admin"))
        markup.add(types.InlineKeyboardButton(text="Удалить админа", callback_data="remove_admin"))
    else:
        markup.add(types.InlineKeyboardButton(text="Запустить викторину", callback_data="start_quiz"))
    bot.send_message(call.message.chat.id, "📜 Список команд:", reply_markup=markup)

# Создание викторины
@bot.callback_query_handler(func=lambda call: call.data == "create_quiz")
def create_quiz(call):
    if is_admin(call.from_user.id):
        msg = bot.send_message(call.message.chat.id, "Введите название викторины:")
        bot.register_next_step_handler(msg, process_quiz_name, call.from_user.id)
    else:
        bot.answer_callback_query(call.id, "❌ У вас нет прав для выполнения этой команды.")

def process_quiz_name(message, user_id):
    quiz_name = message.text
    temp_data[user_id] = {'quiz_name': quiz_name, 'questions': []}
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="Добавить вопрос", callback_data="add_question"))
    markup.add(types.InlineKeyboardButton(text="Завершить создание", callback_data="finish_quiz"))
    markup.add(types.InlineKeyboardButton(text="Назад", callback_data="back_to_main"))
    bot.send_message(message.chat.id, f"Викторина '{quiz_name}' создана. Что дальше?", reply_markup=markup)

# Добавление вопроса
@bot.callback_query_handler(func=lambda call: call.data == "add_question")
def add_question(call):
    if is_admin(call.from_user.id):
        msg = bot.send_message(call.message.chat.id, "Введите вопрос:")
        bot.register_next_step_handler(msg, process_question, call.from_user.id)
    else:
        bot.answer_callback_query(call.id, "❌ У вас нет прав для выполнения этой команды.")

def process_question(message, user_id):
    question = message.text
    temp_data[user_id]['questions'].append({'question': question, 'answer': None, 'photo': None})
    msg = bot.send_message(message.chat.id, "Введите ответ на этот вопрос:")
    bot.register_next_step_handler(msg, process_answer, user_id)

def process_answer(message, user_id):
    answer = message.text
    temp_data[user_id]['questions'][-1]['answer'] = answer
    msg = bot.send_message(message.chat.id, "Хотите добавить фото к вопросу? (Отправьте фото или напишите 'нет')")
    bot.register_next_step_handler(msg, process_photo, user_id)

def process_photo(message, user_id):
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

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="Добавить еще вопрос", callback_data="add_question"))
    markup.add(types.InlineKeyboardButton(text="Завершить викторину", callback_data="finish_quiz"))
    markup.add(types.InlineKeyboardButton(text="Назад", callback_data="back_to_main"))
    bot.send_message(message.chat.id, "Что дальше?", reply_markup=markup)

# Завершение создания викторины
@bot.callback_query_handler(func=lambda call: call.data == "finish_quiz")
def finish_quiz(call):
    if is_admin(call.from_user.id):
        user_id = call.from_user.id
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
        bot.send_message(call.message.chat.id, f"Викторина '{quiz_name}' успешно сохранена!")
        del temp_data[user_id]
    else:
        bot.answer_callback_query(call.id, "❌ У вас нет прав для выполнения этой команды.")

# Редактирование викторины
@bot.callback_query_handler(func=lambda call: call.data == "edit_quiz")
def edit_quiz(call):
    if is_admin(call.from_user.id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM quizzes WHERE admin_id = %s", (call.from_user.id,))
        quizzes = cursor.fetchall()
        conn.close()

        if not quizzes:
            bot.send_message(call.message.chat.id, "Нет доступных викторин для редактирования.")
            return

        markup = types.InlineKeyboardMarkup()
        for quiz in quizzes:
            markup.add(types.InlineKeyboardButton(text=quiz[1], callback_data=f"edit_quiz_{quiz[0]}"))
        markup.add(types.InlineKeyboardButton(text="Назад", callback_data="back_to_main"))
        bot.send_message(call.message.chat.id, "Выберите викторину для редактирования:", reply_markup=markup)
    else:
        bot.answer_callback_query(call.id, "❌ У вас нет прав для выполнения этой команды.")

# Выбор вопроса для редактирования
@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_quiz_"))
def edit_quiz_questions(call):
    if is_admin(call.from_user.id):
        quiz_id = int(call.data.split("_")[2])
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, question FROM questions WHERE quiz_id = %s", (quiz_id,))
        questions = cursor.fetchall()
        conn.close()

        if not questions:
            bot.send_message(call.message.chat.id, "В этой викторине нет вопросов.")
            return

        markup = types.InlineKeyboardMarkup()
        for question in questions:
            markup.add(types.InlineKeyboardButton(text=question[1], callback_data=f"edit_question_{question[0]}"))
        markup.add(types.InlineKeyboardButton(text="Назад", callback_data="edit_quiz"))
        bot.send_message(call.message.chat.id, "Выберите вопрос для редактирования:", reply_markup=markup)
    else:
        bot.answer_callback_query(call.id, "❌ У вас нет прав для выполнения этой команды.")

# Редактирование вопроса
@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_question_"))
def edit_question(call):
    if is_admin(call.from_user.id):
        # Извлекаем question_id из call.data
        question_id = int(call.data.split("_")[2])
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT question, answer, photo, quiz_id FROM questions WHERE id = %s", (question_id,))
        question_data = cursor.fetchone()
        conn.close()

        if not question_data:
            bot.send_message(call.message.chat.id, "❌ Вопрос не найден.")
            return

        question, answer, photo, quiz_id = question_data
        temp_data[call.from_user.id] = {
            'question_id': question_id,
            'question': question,
            'answer': answer,
            'photo': photo,
            'quiz_id': quiz_id  # Сохраняем quiz_id для возврата
        }

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text="Изменить текст вопроса", callback_data=f"edit_text_{question_id}"))
        markup.add(types.InlineKeyboardButton(text="Изменить ответ", callback_data=f"edit_answer_{question_id}"))
        markup.add(types.InlineKeyboardButton(text="Изменить фото", callback_data=f"edit_photo_{question_id}"))
        markup.add(types.InlineKeyboardButton(text="Назад", callback_data=f"edit_quiz_{quiz_id}"))  # Возврат к списку вопросов

        if photo:
            bot.send_photo(call.message.chat.id, photo, caption=f"📝 Вопрос: {question}\n✅ Ответ: {answer}", reply_markup=markup)
        else:
            bot.send_message(call.message.chat.id, f"📝 Вопрос: {question}\n✅ Ответ: {answer}", reply_markup=markup)
    else:
        bot.answer_callback_query(call.id, "❌ У вас нет прав для выполнения этой команды.")

# Изменение текста вопроса
@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_text_"))
def edit_question_text(call):
    if is_admin(call.from_user.id):
        question_id = int(call.data.split("_")[2])
        msg = bot.send_message(call.message.chat.id, "Введите новый текст вопроса:")
        bot.register_next_step_handler(msg, process_edit_question_text, question_id)
    else:
        bot.answer_callback_query(call.id, "❌ У вас нет прав для выполнения этой команды.")

def process_edit_question_text(message, question_id):
    new_question = message.text
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE questions SET question = %s WHERE id = %s", (new_question, question_id))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ Текст вопроса успешно изменен.")
    edit_question(message)  # Возвращаемся к меню редактирования вопроса

# Изменение ответа на вопрос
@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_answer_"))
def edit_question_answer(call):
    if is_admin(call.from_user.id):
        question_id = int(call.data.split("_")[2])
        msg = bot.send_message(call.message.chat.id, "Введите новый ответ на вопрос:")
        bot.register_next_step_handler(msg, process_edit_question_answer, question_id)
    else:
        bot.answer_callback_query(call.id, "❌ У вас нет прав для выполнения этой команды.")

def process_edit_question_answer(message, question_id):
    new_answer = message.text
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE questions SET answer = %s WHERE id = %s", (new_answer, question_id))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ Ответ на вопрос успешно изменен.")
    edit_question(message)  # Возвращаемся к меню редактирования вопроса

# Изменение фото вопроса
@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_photo_"))
def edit_question_photo(call):
    if is_admin(call.from_user.id):
        question_id = int(call.data.split("_")[2])
        msg = bot.send_message(call.message.chat.id, "Отправьте новое фото для вопроса (или напишите 'нет', чтобы удалить фото):")
        bot.register_next_step_handler(msg, process_edit_question_photo, question_id)
    else:
        bot.answer_callback_query(call.id, "❌ У вас нет прав для выполнения этой команды.")

def process_edit_question_photo(message, question_id):
    if message.photo:
        new_photo = message.photo[-1].file_id
    else:
        new_photo = None

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE questions SET photo = %s WHERE id = %s", (new_photo, question_id))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ Фото вопроса успешно изменено.")
    edit_question(message)  # Возвращаемся к меню редактирования вопроса

# Удаление викторины
@bot.callback_query_handler(func=lambda call: call.data == "delete_quiz")
def delete_quiz(call):
    if is_admin(call.from_user.id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM quizzes WHERE admin_id = %s", (call.from_user.id,))
        quizzes = cursor.fetchall()
        conn.close()

        if not quizzes:
            bot.send_message(call.message.chat.id, "Нет доступных викторин для удаления.")
            return

        markup = types.InlineKeyboardMarkup()
        for quiz in quizzes:
            markup.add(types.InlineKeyboardButton(text=quiz[1], callback_data=f"delete_quiz_{quiz[0]}"))
        markup.add(types.InlineKeyboardButton(text="Назад", callback_data="back_to_main"))
        bot.send_message(call.message.chat.id, "Выберите викторину для удаления:", reply_markup=markup)
    else:
        bot.answer_callback_query(call.id, "❌ У вас нет прав для выполнения этой команды.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_quiz_"))
def process_delete_quiz(call):
    if is_admin(call.from_user.id):
        quiz_id = int(call.data.split("_")[2])
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM quizzes WHERE id = %s", (quiz_id,))
        conn.commit()
        conn.close()
        bot.send_message(call.message.chat.id, "Викторина успешно удалена.")
    else:
        bot.answer_callback_query(call.id, "❌ У вас нет прав для выполнения этой команды.")

# Добавление админа
@bot.callback_query_handler(func=lambda call: call.data == "add_admin")
def add_admin(call):
    if is_admin(call.from_user.id):
        msg = bot.send_message(call.message.chat.id, "Перешлите любое сообщение от пользователя, которого нужно сделать админом.")
        bot.register_next_step_handler(msg, process_add_admin)
    else:
        bot.answer_callback_query(call.id, "❌ У вас нет прав для выполнения этой команды.")

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
@bot.callback_query_handler(func=lambda call: call.data == "remove_admin")
def remove_admin(call):
    if is_admin(call.from_user.id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM admins")
        admins = cursor.fetchall()
        conn.close()

        if not admins:
            bot.send_message(call.message.chat.id, "Нет доступных админов для удаления.")
            return

        markup = types.InlineKeyboardMarkup()
        for admin in admins:
            markup.add(types.InlineKeyboardButton(text=f"@{admin[0]}", callback_data=f"remove_admin_{admin[0]}"))
        markup.add(types.InlineKeyboardButton(text="Назад", callback_data="back_to_main"))
        bot.send_message(call.message.chat.id, "Выберите админа для удаления:", reply_markup=markup)
    else:
        bot.answer_callback_query(call.id, "❌ У вас нет прав для выполнения этой команды.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("remove_admin_"))
def process_remove_admin(call):
    if is_admin(call.from_user.id):
        username = call.data.split("_")[2]
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM admins WHERE username = %s", (username,))
        conn.commit()
        conn.close()
        bot.send_message(call.message.chat.id, f"Админ @{username} удален.")
    else:
        bot.answer_callback_query(call.id, "❌ У вас нет прав для выполнения этой команды.")


# Кнопка "Назад"
@bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
def back_to_main(call):
    start_command(call.message)

# Запуск викторины
@bot.callback_query_handler(func=lambda call: call.data == "start_quiz")
def start_quiz(call):
    if is_admin(call.from_user.id):  # Проверка, является ли пользователь админом
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM quizzes")
        quizzes = cursor.fetchall()
        conn.close()

        if not quizzes:
            bot.send_message(call.message.chat.id, "Нет доступных викторин.")
            return

        markup = types.InlineKeyboardMarkup()
        for quiz in quizzes:
            markup.add(types.InlineKeyboardButton(text=quiz[1], callback_data=f"start_quiz_{quiz[0]}"))
        markup.add(types.InlineKeyboardButton(text="Назад", callback_data="back_to_main"))
        bot.send_message(call.message.chat.id, "Выберите викторину для запуска:", reply_markup=markup)
    else:
        bot.answer_callback_query(call.id, "❌ У вас нет прав для выполнения этой команды.")

# Обработка запуска викторины
@bot.callback_query_handler(func=lambda call: call.data.startswith("start_quiz_"))
def process_start_quiz(call):
    quiz_id = int(call.data.split("_")[2])
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM quizzes WHERE id = %s", (quiz_id,))
    quiz_name = cursor.fetchone()[0]
    conn.close()

    active_quizzes[call.message.chat.id] = {
        'quiz_id': quiz_id,
        'current_question': 0,
        'scores': defaultdict(int),
        'current_answer': None
    }

    bot.send_message(call.message.chat.id, f"🎉 Викторина '{quiz_name}' начнется через 15 секунд! Приготовьтесь!")
    time.sleep(15)
    ask_question(call.message.chat.id, quiz_id)

# Задать вопрос
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
    active_quizzes[chat_id]['current_answer'] = answer.lower()

    if photo:
        bot.send_photo(chat_id, photo, caption=f"❓ Вопрос {current_question + 1}: {question}")
    else:
        bot.send_message(chat_id, f"❓ Вопрос {current_question + 1}: {question}")

# Обработка ответов
@bot.message_handler(func=lambda message: message.chat.id in active_quizzes)
def handle_answer(message):
    chat_id = message.chat.id

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

        active_quizzes[chat_id]['current_question'] += 1
        time.sleep(5)
        ask_question(chat_id, active_quizzes[chat_id]['quiz_id'])

# Показать результаты
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

# Завершение викторины
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
