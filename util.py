import traceback

from telegram import *
from telegram import Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import ContextTypes


# Обробляємо помилки
async def error_handler(update, context):
    # Можна показати traceback у консолі
    traceback.print_exception(type(context.error), context.error, context.error.__traceback__)

    try:
        if update and update.effective_message:
            args = context.error.args
            if args and len(args) > 0:
                message = str(args[1]) if len(args) > 1 else str(args[0])
            else:
                message = str(context.error)
            await update.effective_message.reply_text(f"⚠️ {message}")
    except TelegramError:
        pass  # якщо повідомлення вже видалено або чат недоступний


# Надсилає в чат текстове повідомлення
async def send_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> Message:
    if text.count('_') % 2 != 0:
        message = f"Рядок '{text}' є невалідним з точки зору markdown. Скористайтеся методом send_html()"
        print(message)
        return await update.message.reply_text(message)

    text = text.encode('utf16', errors='surrogatepass').decode('utf16')
    return await context.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode=ParseMode.MARKDOWN)


# надсилає в чат HTML-повідомлення
async def send_html(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> Message:
    text = text.encode('utf16', errors='surrogatepass').decode('utf16')
    return await context.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode=ParseMode.HTML)


# надсилає в чат текстове повідомлення та додає до нього кнопки
async def send_text_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, buttons: dict,
                            checkbox_key: str = None) -> Message:
    text = text.encode('utf16', errors='surrogatepass').decode('utf16')
    keyboard = []
    for key, value in buttons.items():
        title = f"{value} ✅" if checkbox_key == key else str(value)
        button = InlineKeyboardButton(title, callback_data=str(key))
        keyboard.append([button])
    reply_markup = InlineKeyboardMarkup(keyboard)
    return await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)


# Змінює наявне повідомлення з кнопками
async def edit_text_buttons(message: Message, text: str, buttons: dict, checkbox_key: str = None) -> Message:
    text = text.encode('utf16', errors='surrogatepass').decode('utf16')
    keyboard = []
    for key, value in buttons.items():
        title = f"{value} ✅" if checkbox_key == key else str(value)
        button = InlineKeyboardButton(title, callback_data=str(key))
        keyboard.append([button])
    reply_markup = InlineKeyboardMarkup(keyboard)

    if message.text == text:
        return await message.edit_reply_markup(reply_markup=reply_markup)
    else:
        return await message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)


# надсилає в чат фото
async def send_photo(update: Update, context: ContextTypes.DEFAULT_TYPE, name: str) -> Message:
    path = name if "/" in name else f"resources/images/{name}.jpg"
    with open(path, 'rb') as photo:
        return await context.bot.send_photo(chat_id=update.effective_chat.id, photo=photo)


# надсилає в чат відео
async def send_video(update: Update, context: ContextTypes.DEFAULT_TYPE, name: str) -> Message:
    path = name if "/" in name else f"resources/videos/{name}.mp4"
    with open(path, 'rb') as video:
        return await context.bot.send_video(chat_id=update.effective_chat.id, video=video)


# відображає команду та головне меню
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, commands: dict):
    command_list = [BotCommand(key, value) for key, value in commands.items()]
    await context.bot.set_my_commands(command_list, scope=BotCommandScopeChat(chat_id=update.effective_chat.id))
    await context.bot.set_chat_menu_button(menu_button=MenuButtonCommands(), chat_id=update.effective_chat.id)


# Видаляємо команди для конкретного чату
async def hide_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.delete_my_commands(scope=BotCommandScopeChat(chat_id=update.effective_chat.id))
    await context.bot.set_chat_menu_button(menu_button=MenuButtonDefault(), chat_id=update.effective_chat.id)


# завантажує повідомлення з папки  /resources/messages/
def load_message(name):
    with open("resources/messages/" + name + ".txt", "r", encoding="utf8") as file:
        return file.read()


# завантажує промпт з папки  /resources/messages/
def load_prompt(name):
    with open("resources/prompts/" + name + ".txt", "r", encoding="utf8") as file:
        return file.read()

# Сесія користувача
class UserSession:
    def __init__(self):
        self.mode = None

session = UserSession()

