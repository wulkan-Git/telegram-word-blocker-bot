import logging
import re
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import config  # <-- импорт из config.py

# --- Настройка логирования ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- Константы из конфига ---
TOKEN = config.TOKEN
ADMIN_IDS = set(config.ADMIN_IDS)
WHITELISTED_USER_IDS = set(config.WHITELISTED_USER_IDS)
WORDS_FILE = "banned_words.txt"

# --- Загрузка запрещённых слов ---
def load_banned_words() -> list:
    patterns = []
    try:
        with open(WORDS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                word = line.strip()
                if word and not word.startswith("#"):
                    if any(c in word for c in ('\\b', '\\w', '^', '$', r'\d')):
                        pattern = word
                    else:
                        pattern = f'\\b{re.escape(word)}\\b'
                    patterns.append(re.compile(pattern, re.IGNORECASE))
    except Exception as e:
        logger.error(f"Ошибка загрузки слов: {e}")
    return patterns

def save_banned_word(word: str):
    with open(WORDS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{word}\n")

banned_patterns = load_banned_words()

# --- Команды ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛡️ Бот слежения за запрещёнными словами активен.\n"
        "Администраторы могут добавлять слова через /banword."
    )

async def banword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав.")
        return

    if not context.args:
        await update.message.reply_text("📌 Пример: /banword казино")
        return

    word = ' '.join(context.args)
    save_banned_word(word)
    global banned_patterns
    banned_patterns = load_banned_words()

    await update.message.reply_text(f"✅ Добавлено: `{word}`", parse_mode='Markdown')
    logger.info(f"Админ {user_id} добавил: {word}")

# --- Проверка сообщений ---
async def check_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    chat = message.chat
    user = message.from_user

    if chat.type not in ['group', 'supergroup']:
        return

    if user.id in WHITELISTED_USER_IDS:
        return

    text = (message.text or message.caption or "").strip()
    if not text:
        return

    for pattern in banned_patterns:
        if pattern.search(text):
            matched = pattern.pattern
            try:
                await context.bot.ban_chat_member(chat_id=chat.id, user_id=user.id)
                await message.reply_text(
                    f"🚫 @{user.username or user.id} заблокирован.\n"
                    f"Причина: `{matched}`",
                    parse_mode='Markdown'
                )
                logger.info(f"Забанен {user.id} за: {matched}")
            except Exception as e:
                logger.error(f"Ошибка бана {user.id}: {e}")
            break

# --- Запуск ---
def main():
    global banned_patterns
    banned_patterns = load_banned_words()
    logger.info(f"Загружено {len(banned_patterns)} шаблонов.")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("banword", banword))
    app.add_handler(MessageHandler(filters.ALL, check_message))

    logger.info("Бот запущен...")
    app.run_polling()

if __name__ == '__main__':
    main()
