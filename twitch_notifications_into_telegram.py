import json
import mimetypes
import os
import urllib.parse
import urllib.request

import obspython as obs

BASE_URL = "https://api.telegram.org/bot{token}/"
URL_SEND_MSG = BASE_URL + "sendMessage"
URL_DELETE_MSG = BASE_URL + "deleteMessage"
URL_SEND_PHOTO = BASE_URL + "sendPhoto"

FILTER_ALL_FILES = "Все файлы (*.*)"
FILTER_PHOTO = '*.jpg *.jpeg *.png *.gif '

bot_token = ""
chat_id = ""
start_message = ""
end_message = ""
enable_start = True
enable_end = True
delete_start_message = False
disable_web_page_preview = True
attach_photo = ""
is_group_attach_photo = False

sent_message_ids = {
    "start_message": None
}


class TelegramBot:
    def __init__(self, token, chat):
        self.bot_token = token
        self.chat_id = chat

    def send_msg(self, msg_text):
        """Отправка сообщения через urllib"""
        if not self.bot_token or not self.chat_id:
            return False

        url = URL_SEND_MSG.format(token=self.bot_token)
        data = urllib.parse.urlencode({
            'disable_web_page_preview': disable_web_page_preview,
            'chat_id': self.chat_id,
            'text': msg_text,
            'parse_mode': 'HTML'
        }).encode('utf-8')
        try:
            with urllib.request.urlopen(url=urllib.request.Request(url, data=data), timeout=10) as response:
                response = json.loads(response.read().decode())
                message_id = response.get("result").get("message_id")
                sent_message_ids["start_message"] = message_id
                return response.get('ok')
        except Exception:
            return False

    def delete_msg(self, message_id):
        """Удаление сообщения через urllib"""
        if not message_id or bot_token == "" or chat_id == "":
            return False
        url = URL_DELETE_MSG.format(token=self.bot_token)
        data = urllib.parse.urlencode({
            'chat_id': self.chat_id,
            'message_id': message_id,
            'parse_mode': 'HTML'
        }).encode('utf-8')
        try:
            with urllib.request.urlopen(url=urllib.request.Request(url, data=data), timeout=10) as response:
                response = json.loads(response.read().decode())
                return response.get('ok')
        except Exception:
            return False

    def delete_start_msg(self):
        """Удаление стартового сообщения"""
        if sent_message_ids.get("start_message"):
            success = self.delete_msg(sent_message_ids["start_message"])
            if success:
                sent_message_ids["start_message"] = None
            return success
        return False

    def send_photo(self, image_path, caption=""):
        """Отправка фото в Telegram"""
        if not os.path.exists(image_path):
            return f"Файл не найден: {image_path}"

        url = URL_SEND_PHOTO.format(token=self.bot_token)

        try:
            with open(image_path, 'rb') as pic:
                pic_data = pic.read()

            mime_type, _ = mimetypes.guess_type(image_path)
            if not mime_type:
                mime_type = 'image/jpeg'

            boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'

            body = [
                f'--{boundary}',
                'Content-Disposition: form-data; name="chat_id"',
                '',
                str(self.chat_id),
                f'--{boundary}',
                f'Content-Disposition: form-data; name="photo"; filename="{os.path.basename(image_path)}"',
                f'Content-Type: {mime_type}',
                '',
            ]

            body = '\r\n'.join(body).encode('utf-8') + b'\r\n' + pic_data + b'\r\n'

            if caption:
                body += f'--{boundary}\r\n'.encode('utf-8')
                body += b'Content-Disposition: form-data; name="caption"\r\n\r\n'
                body += caption.encode('utf-8') + b'\r\n'

                body += f'--{boundary}\r\n'.encode('utf-8')
                body += b'Content-Disposition: form-data; name="parse_mode"\r\n\r\n'
                body += b'HTML\r\n'

            body += f'--{boundary}--\r\n'.encode('utf-8')
            req = urllib.request.Request(
                url,
                data=body,
                headers={'Content-Type': f'multipart/form-data; boundary={boundary}', 'User-Agent': 'OBS-Studio'}
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                response = json.loads(response.read().decode())
                message_id = response.get("result").get("message_id")
                sent_message_ids["start_message"] = message_id
                return response.get('ok')

        except Exception as e:
            return f"Ошибка отправки фото: {str(e)}"


bot = TelegramBot(bot_token, chat_id)


# region Тестовые прогоны бота
def base_test_stream_callback(default_msg_text, msg_type):
    if not bot.bot_token or not bot.chat_id:
        return False
    if msg_type == "start" and not is_group_attach_photo:
        return bot.send_msg(msg_text=start_message if start_message else default_msg_text)
    elif msg_type == "start" and is_group_attach_photo:
        return bot.send_photo(image_path=attach_photo, caption=start_message if start_message else default_msg_text)
    else:
        if delete_start_message:
            bot.delete_start_msg()
        return bot.send_msg(msg_text=end_message if end_message else default_msg_text) if enable_end else False


def test_start_stream_callback(props, prop):
    """Тест отправки сообщения о начале стрима"""
    return base_test_stream_callback(default_msg_text="Тест: Трансляция началась", msg_type="start")


def test_end_stream_callback(props, prop):
    """Тест отправки сообщения об окончании стрима"""
    return base_test_stream_callback(default_msg_text="Тест: Трансляция завершена", msg_type="end")


# endregion


def on_event(event):
    """Обработчик событий OBS"""
    if event == obs.OBS_FRONTEND_EVENT_STREAMING_STARTED:
        if enable_start and start_message and not is_group_attach_photo:
            bot.send_msg(msg_text=start_message)
        elif enable_start and start_message and is_group_attach_photo:
            bot.send_photo(image_path=attach_photo, caption=start_message)

    elif event == obs.OBS_FRONTEND_EVENT_STREAMING_STOPPED:
        if delete_start_message:
            bot.delete_start_msg()

        if enable_end and end_message:
            bot.send_msg(end_message)


def script_description():
    """Описание скрипта"""
    return """<center><h1>Автоматические уведомления в Telegram!</h1></center><hr>
            <p>Этот скрипт отправляет сообщения от лица вашего Telegram-бота о начале/конце вашего стрима 
            в указанные Telegram-каналы, чаты и/или группы.</p>
            <p>В случае, если ваш стрим прервался по независящим от вас причинам 
            и вы не смогли перезапустить его в течение 30 минут, то бот пришлет уведомление о завершении стрима. 
            <p>Заполните форму ниже, протестируйте и начинайте стримить!</p>
            <p>Ознакомиться с исходным кодом проекта можно 
            <a href="https://github.com/SilverSheldon/OBS-python-scripts">здесь</a>.</p>
            <center><p><b>Скрипт работает независимо от вашей операционной системы.</b></p></center>
            <br>
            <center><h2>Настройка оповещений</h2></center><hr>
            """


def script_properties():
    """Создание интерфейса настроек"""
    props = obs.obs_properties_create()

    # region Настройка сообщения при запуске стрима
    group_start_msg = obs.obs_properties_create()

    start_msg = obs.obs_properties_add_text(
        group_start_msg,
        name="start_message",
        description="Сообщение при старте",
        type=obs.OBS_TEXT_MULTILINE
    )
    obs.obs_property_set_long_description(
        start_msg,
        "Это сообщение будет отправлено в Telegram-канал/группу/чат при начале трансляции.\nПоддерживается HTML-форматирование."
    )

    start_check = obs.obs_properties_add_bool(
        group_start_msg,
        name="enable_start",
        description="Отправить при старте"
    )
    obs.obs_property_set_long_description(
        start_check,
        "Отправлять это сообщение при начале трансляции"
    )

    delete_check = obs.obs_properties_add_bool(
        group_start_msg,
        name="delete_start_message",
        description="Удалить после окончания"
    )
    obs.obs_property_set_long_description(
        delete_check,
        "Удалить это сообщение после окончания стрима"
    )

    group_attach_photo = obs.obs_properties_create()
    attach_photo_path = obs.obs_properties_add_path(
        group_attach_photo,
        name="attach_photo",
        description="Прикрепить фото (путь к файлу)",
        type=obs.OBS_TEXT_DEFAULT,
        filter=FILTER_PHOTO,
        default_path=''
    )
    obs.obs_property_set_long_description(
        attach_photo_path,
        "По желанию вы можете прикрепить путь к фото, которое будет отправлено вместе с сообщением"
    )

    disable_web_page_prev = obs.obs_properties_add_bool(
        group_start_msg,
        name="disable_web_page_preview",
        description="Ссылки без превью (не работает, если прикреплено фото)"
    )
    obs.obs_property_set_long_description(
        disable_web_page_prev,
        "Если к сообщению прикреплена ссылка, то со включенной галочкой отправится превью ссылки (картинка)"
    )

    obs.obs_properties_add_group(
        group_start_msg,
        name="group_attach_photo",
        description="ПРИКРЕПИТЬ ФОТО (необязательно)",
        type=obs.OBS_GROUP_CHECKABLE,
        group=group_attach_photo
    )

    obs.obs_properties_add_group(
        props,
        name="start_msg_settings",
        description="ЗАПУСК СТРИМА",
        type=obs.OBS_GROUP_NORMAL,
        group=group_start_msg
    )
    # endregion

    # region Настройка сообщения после окончания стрима
    group_end_msg = obs.obs_properties_create()

    end_msg = obs.obs_properties_add_text(
        group_end_msg,
        name="end_message",
        description="Сообщение при окончании",
        type=obs.OBS_TEXT_MULTILINE
    )
    obs.obs_property_set_long_description(
        end_msg,
        "Это сообщение будет отправлено в Telegram-канал/группу/чат при завершении трансляции"
    )

    end_check = obs.obs_properties_add_bool(
        group_end_msg,
        name="enable_end",
        description="Отправить при окончании"
    )
    obs.obs_property_set_long_description(
        end_check,
        "Отправлять это сообщение при окончании трансляции"
    )

    obs.obs_properties_add_group(
        props,
        name="end_msg_settings",
        description="ЗАВЕРШЕНИЕ СТРИМА",
        type=obs.OBS_GROUP_NORMAL,
        group=group_end_msg
    )
    # endregion

    # region Подключение бота
    group_bot_connect = obs.obs_properties_create()

    token = obs.obs_properties_add_text(
        group_bot_connect,
        name="bot_token",
        description="Токен бота",
        type=obs.OBS_TEXT_PASSWORD
    )
    obs.obs_property_set_long_description(
        token,
        "Скопируйте сюда токен Telegram-бота, полученный от @BotFather (например: 0123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdefghijklmnopqrstuvwxyz)"
    )

    chat = obs.obs_properties_add_text(
        group_bot_connect,
        name="chat_id",
        description="ID канала/чата",
        type=obs.OBS_TEXT_PASSWORD
    )
    obs.obs_property_set_long_description(
        chat,
        "Скопируйте сюда ID своего Telegram-канала/группы/чата (например: -1001234567890)"
    )

    obs.obs_properties_add_group(
        props,
        name="bot_settings",
        description="ПОДКЛЮЧЕНИЕ БОТА",
        type=obs.OBS_GROUP_NORMAL,
        group=group_bot_connect
    )
    # endregion

    # region Тестовый прогон бота
    group_bot_test = obs.obs_properties_create()

    test_start = obs.obs_properties_add_button(
        group_bot_test,
        "test_start_button",
        "Тест: 🎬 Старт стрима",
        test_start_stream_callback
    )
    obs.obs_property_set_long_description(
        test_start,
        "Отправить тестовое сообщение о начале трансляции. Учитывает настройку удаления сообщения."
    )

    test_end = obs.obs_properties_add_button(
        group_bot_test,
        "test_end_button",
        "Тест: 🛑 Конец стрима",
        test_end_stream_callback
    )
    obs.obs_property_set_long_description(
        test_end,
        "Отправить тестовое сообщение об окончании трансляции"
    )

    obs.obs_properties_add_group(
        props,
        name="bot_test",
        description="ТЕСТОВЫЙ ПРОГОН БОТА (в Telegram-канал/группу придёт фейковое уведомление)",
        type=obs.OBS_GROUP_NORMAL,
        group=group_bot_test
    )
    # endregion

    # region Более подробная инструкция для маленьких и тупых
    group_instruction = obs.obs_properties_create()

    instructions_text = """
    <ol>
        <li>
            <b>СОЗДАЙТЕ БОТА:</b>
            <ul>
                <li><i>Найдите @BotFather в Telegram</i></li>
                <li><i>Отправьте /newbot</i></li>
                <li><i>Следуя его инструкциям, введите имя и username бота</i></li>
                <li><i>Скопируйте токен (НИКОМУ НЕ ПЕРЕДАВАЙТЕ!)</i></li>
            </ul>
        </li>
        <br>
        <li>
            <b>ЕСЛИ ВАМ НАДО ДОБАВИТЬ БОТА В:</b>
            <ul>
                <li>Личный чат: <i>напишите боту /start</i></li>
                <li>Группу: <i>добавьте бота как участника</i></li>
                <li>Канал: <i>добавьте бота как администратора</i></li>
            </ul>
        </li>
        <br>
        <li>
            <b>УЗНАЙТЕ ID ЧАТА:</b>
            <ul>
                <li><i>Откройте <a href="https://web.telegram.org">этот сайт</a></i></li>
                <li><i>Перейдите в нужный канал/чат</i></li>
                <li><i>Посмотрите в адресную строку</i></li>
                <li><i>Число после # - это ID вашего канала/чата</i></li>
                <li><i>Или вы можете использовать ботов по типу <a href="https://t.me/userinfobot">userinfobot</a></i></li>
                <li>
                    ПРИМЕРЫ:
                    <ul>
                        <li>ID личного чата: <i>123456789</i></li>
                        <li>ID канала/группы: <i>-1001234567890</i></li>
                        <li>Токен бота: <i>0123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdefghijklmnopqrstuvwxyz</i></li>
                    </ul>
                </li>
            </ul>
        </li>
        <br>
        <li>
            <b>НАСТРОЙТЕ ВСЁ НЕОБХОДИМОЕ В OBS:</b>
            <ul>
                <li><i>Настройте сообщения</i></li>
                <li><i>Включите нужные опции</i></li>
                <li><i>Вставьте токен и chat_id</i></li>
                <li><i>Протестируйте кнопками</i></li>
            </ul>
        </li>
    </ol>
    <br>
    <hr>
    <h3>ВАЖНО:</h3>
    <ul>
        <li><h4>Бот должен иметь права на отправку сообщений</h4></li>
        <li><h4>В канале у бота должны быть права администратора</h4></li>
        <li><h4>ID каналов всегда отрицательный (начинается с <i>-100...</i>)</h4></li>
        <li><h4>Не забывайте сохранить настройки после ввода</h4></li>
    </ul>
    """

    obs.obs_properties_add_text(
        group_instruction,
        name="instructions",
        description=instructions_text,
        type=obs.OBS_TEXT_INFO
    )
    obs.obs_properties_add_group(
        props,
        name="instruction",
        description="ПОДРОБНАЯ ИНСТРУКЦИЯ ПО НАСТРОЙКЕ СКРИПТА",
        type=obs.OBS_GROUP_NORMAL,
        group=group_instruction
    )
    # endregion

    return props


def script_defaults(settings):
    """Установка значений по умолчанию"""
    obs.obs_data_set_default_string(settings, "bot_token", "")
    obs.obs_data_set_default_string(settings, "chat_id", "")

    default_start_msg = '🎥 НУ ЧЕ, НАРОД, ПОГНАЛИ? ВСЕ НА <a href="https://www.twitch.tv/jitterbug_jemboree">СТРИМ!</a>'
    default_end_msg = "🛑 ВСЕМ СПАСИБО ЗА СТРИМ!"

    obs.obs_data_set_default_string(settings, "start_message", default_start_msg)
    obs.obs_data_set_default_string(settings, "end_message", default_end_msg)

    obs.obs_data_set_default_string(settings, "attach_photo", "")

    obs.obs_data_set_default_bool(settings, "enable_start", True)
    obs.obs_data_set_default_bool(settings, "delete_start_message", False)

    obs.obs_data_set_default_bool(settings, "enable_end", True)

    obs.obs_data_set_default_bool(settings, "disable_web_page_preview", True)


def script_load(settings):
    """Загрузка скрипта"""
    global bot_token, chat_id, start_message, end_message, enable_start, enable_end, delete_start_message
    global disable_web_page_preview, attach_photo, is_group_attach_photo

    bot_token = obs.obs_data_get_string(settings, "bot_token")
    chat_id = obs.obs_data_get_string(settings, "chat_id")

    start_message = obs.obs_data_get_string(settings, "start_message")
    end_message = obs.obs_data_get_string(settings, "end_message")

    enable_start = obs.obs_data_get_bool(settings, "enable_start")
    delete_start_message = obs.obs_data_get_bool(settings, "delete_start_message")

    enable_end = obs.obs_data_get_bool(settings, "enable_end")

    if is_group_attach_photo:
        attach_photo = obs.obs_data_get_bool(settings, "attach_photo")

    disable_web_page_preview = obs.obs_data_get_bool(settings, "disable_web_page_preview")

    # Сброс сохраненных ID сообщений
    sent_message_ids["start_message"] = None

    # Регистрация обработчика событий
    obs.obs_frontend_add_event_callback(on_event)


def script_update(settings):
    """Обновление настроек в реальном времени. Например, поставил галочку в чекбокс - изменения тут же применились."""
    global bot_token, chat_id, start_message, end_message, enable_start, delete_start_message, enable_end
    global disable_web_page_preview, attach_photo, is_group_attach_photo

    bot_token = bot.bot_token = obs.obs_data_get_string(settings, "bot_token")
    chat_id = bot.chat_id = obs.obs_data_get_string(settings, "chat_id")

    start_message = obs.obs_data_get_string(settings, "start_message")
    end_message = obs.obs_data_get_string(settings, "end_message")

    is_group_attach_photo = obs.obs_data_get_bool(settings, "group_attach_photo")
    if is_group_attach_photo:
        attach_photo = obs.obs_data_get_string(settings, "attach_photo")

    enable_start = obs.obs_data_get_bool(settings, "enable_start")
    delete_start_message = obs.obs_data_get_bool(settings, "delete_start_message")

    enable_end = obs.obs_data_get_bool(settings, "enable_end")

    disable_web_page_preview = obs.obs_data_get_bool(settings, "disable_web_page_preview")


def script_save(settings):
    """Сохранение настроек"""
    obs.obs_data_set_string(settings, "bot_token", bot_token)
    obs.obs_data_set_string(settings, "chat_id", chat_id)

    obs.obs_data_set_string(settings, "start_message", start_message)
    obs.obs_data_set_string(settings, "end_message", end_message)

    if is_group_attach_photo:
        obs.obs_data_set_string(settings, "attach_photo", attach_photo)

    obs.obs_data_set_bool(settings, "enable_start", enable_start)
    obs.obs_data_set_bool(settings, "delete_start_message", delete_start_message)

    obs.obs_data_set_bool(settings, "enable_end", enable_end)

    obs.obs_data_set_bool(settings, "disable_web_page_preview", disable_web_page_preview)


def script_unload():
    """Выгрузка скрипта"""
    pass  # Очистка ресурсов при необходимости
