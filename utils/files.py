"""
Habesha Build Hub — File Utility Layer
Handles all file sending, preview detection, and type validation.
Centralises file logic so every bot uses the same safe implementation.
"""

import logging
from telegram import Bot, Message
from telegram.error import TelegramError, BadRequest

logger = logging.getLogger(__name__)

# ── Allowed file extensions ────────────────────────────────────────────────────
ALLOWED_EXTENSIONS = {
    # Documents
    '.pdf', '.xlsx', '.xls', '.csv',
    '.doc', '.docx', '.txt',
    # Images
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp',
    # Drawings / CAD
    '.dwg', '.dxf', '.svg',
}

MAX_FILE_SIZE_MB = 20   # Telegram bot limit is 50MB but we cap at 20 for stability

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}


def get_file_ext(filename: str) -> str:
    """Return lowercase extension including the dot, e.g. '.pdf'"""
    if not filename:
        return ''
    idx = filename.rfind('.')
    return filename[idx:].lower() if idx >= 0 else ''


def is_image(filename: str) -> bool:
    return get_file_ext(filename) in IMAGE_EXTENSIONS


def is_allowed(filename: str) -> bool:
    ext = get_file_ext(filename)
    return ext in ALLOWED_EXTENSIONS or ext == ''   # no extension = allow


def file_type_label(filename: str) -> str:
    ext = get_file_ext(filename)
    labels = {
        '.pdf':  'PDF Document',
        '.xlsx': 'Excel Spreadsheet',
        '.xls':  'Excel Spreadsheet',
        '.csv':  'CSV File',
        '.doc':  'Word Document',
        '.docx': 'Word Document',
        '.jpg':  'Image',
        '.jpeg': 'Image',
        '.png':  'Image',
        '.gif':  'Image',
        '.dwg':  'Drawing File',
        '.dxf':  'Drawing File',
    }
    return labels.get(ext, 'File')


async def send_file_preview(
    bot: Bot,
    chat_id: int,
    file_id: str,
    filename: str,
    caption: str = '',
    parse_mode: str = 'Markdown'
) -> bool:
    """
    Send a file to a chat with proper Telegram-native preview.
    - Images are sent as photos (shows preview in chat)
    - Documents are sent as documents (shows file icon + name)
    Returns True on success, False on failure.
    """
    try:
        if is_image(filename):
            # Send as photo — Telegram renders inline preview
            await bot.send_photo(
                chat_id=chat_id,
                photo=file_id,
                caption=caption or f"📎 {filename}",
                parse_mode=parse_mode
            )
        else:
            # Send as document — shows file name, size, download button
            await bot.send_document(
                chat_id=chat_id,
                document=file_id,
                caption=caption or f"📎 {filename}",
                parse_mode=parse_mode,
                filename=filename or None
            )
        return True
    except BadRequest as e:
        logger.warning(f"send_file_preview BadRequest for {file_id}: {e}")
        # File may have expired — inform but don't crash
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=(
                    "⚠️ Could not deliver the file directly.\n\n"
                    f"📎 *File ID:* `{file_id}`\n\n"
                    f"_Use `/getfile {file_id}` to download it._"
                ),
                parse_mode='Markdown'
            )
        except Exception:
            pass
        return False
    except TelegramError as e:
        logger.error(f"send_file_preview TelegramError: {e}")
        return False


async def reply_file_preview(
    message: Message,
    file_id: str,
    filename: str,
    caption: str = '',
    parse_mode: str = 'Markdown'
) -> bool:
    """Same as send_file_preview but replies to a specific message."""
    try:
        if is_image(filename):
            await message.reply_photo(
                photo=file_id,
                caption=caption or f"📎 {filename}",
                parse_mode=parse_mode
            )
        else:
            await message.reply_document(
                document=file_id,
                caption=caption or f"📎 {filename}",
                parse_mode=parse_mode,
                filename=filename or None
            )
        return True
    except BadRequest as e:
        logger.warning(f"reply_file_preview BadRequest: {e}")
        await message.reply_text(
            f"⚠️ Could not preview file.\n\n"
            f"📎 *File ID:* `{file_id}`\n"
            f"_Use `/getfile {file_id}` to download._",
            parse_mode='Markdown'
        )
        return False
    except TelegramError as e:
        logger.error(f"reply_file_preview error: {e}")
        return False


def extract_file_info(message: Message) -> tuple[str, str] | tuple[None, None]:
    """
    Extract (file_id, filename) from any message that contains a file.
    Handles documents, photos, and falls back gracefully.
    Returns (None, None) if no file found.
    """
    if message.document:
        return message.document.file_id, message.document.file_name or 'document'
    if message.photo:
        # Telegram sends multiple sizes — take the largest
        best = message.photo[-1]
        return best.file_id, 'photo.jpg'
    return None, None


def validate_upload(message: Message) -> tuple[bool, str]:
    """
    Validate an incoming file upload.
    Returns (is_valid, error_message).
    """
    file_id, filename = extract_file_info(message)

    if not file_id:
        return False, "No file detected. Please send a file or photo."

    if filename and not is_allowed(filename):
        ext = get_file_ext(filename)
        return False, (
            f"❌ File type *{ext}* is not supported.\n\n"
            f"Accepted formats: Excel, PDF, Word, PNG, JPG, CSV\n\n"
            "_Please send a supported file type._"
        )

    return True, ''
