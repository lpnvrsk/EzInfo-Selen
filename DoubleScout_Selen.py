import os
import sys
import threading
import time
import sqlite3
import signal
import hashlib
import random
import re
from datetime import datetime, date
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from tqdm import tqdm
import logging
from io import StringIO
try:
    from colorama import init, Fore, Back, Style
    init(autoreset=True)
    COLORS_AVAILABLE = True
except ImportError:
    COLORS_AVAILABLE = False
    class Fore:
        GREEN = YELLOW = RED = BLUE = MAGENTA = CYAN = WHITE = BLACK = ''
    class Back:
        GREEN = YELLOW = RED = BLUE = MAGENTA = CYAN = WHITE = BLACK = ''
    class Style:
        BRIGHT = DIM = NORMAL = RESET_ALL = ''

# ==================== КОНФИГУРАЦИЯ ====================
CONFIG = {
    # Режимы работы
    'PLAYTIME_ONLY': False,           # Если True - парсит только по времени игры
    'SAVE_HTML_PAGES': True,          # Если True - сохранять HTML страницы как файлы
    
    # Пути
    'FIREFOX_PROFILE_PATH': r"C:\Users\1111\AppData\Roaming\Mozilla\Firefox\Profiles\ProfileID.default-release",
    'SAVE_DIR': None,                 # Будет создана автоматически
    'LOGS_FOLDER': 'LOGS',
    'BASES_FOLDER': 'BASES',
    
    # Настройки скачивания
    'STEP_SIZE': 20,                  # Шаг пагинации (st=0, 20, 40, ...)
    'MAX_WAIT_TIME': 30,
    'MAX_RETRIES': 3,
    'DELAY_BETWEEN_REQUESTS': 0.5,    # Задержка между запросами
    'RANDOM_DELAY': True,             # Случайная задержка
    'MIN_DELAY': 0.3,
    'MAX_DELAY': 1.2,
    
    # Отладочная информация
    'SAVE_DEBUG_INFO': False,         # Сохранять отладочную информацию
}

# URL
PLAYTIME_URL = "https://ezwow.org/index.php?app=isengard&module=core&tab=armory&section=characters&realm=1&sort%5Bkey%5D=playtime&sort%5Border%5D=desc&st="
NAME_URL = "https://ezwow.org/index.php?app=isengard&module=core&tab=armory&section=characters&realm=1&sort%5Bkey%5D=name&sort%5Border%5D=desc&st="
LAST_PAGE_URL = 'https://ezwow.org/index.php?app=isengard&module=core&tab=armory&section=characters&realm=1&sort%5Bkey%5D=playtime&sort%5Border%5D=desc&st=9999999999999999999'

# Словари перевода
CLASS_TRANSLATION = {
    'Hunter (Охотник)': 'Hunter',
    'Druid (Друид)': 'Druid', 
    'Paladin (Паладин)': 'Paladin',
    'Shaman (Шаман)': 'Shaman',
    'Mage (Маг)': 'Mage',
    'Warrior (Воин)': 'Warrior',
    'Priest (Жрец)': 'Priest',
    'Rogue (Разбойник)': 'Rogue',
    'Death knight (Рыцарь смерти)': 'Death Knight',
    'Warlock (Чернокнижник)': 'Warlock'
}

RACE_TRANSLATION = {
    'Дренеи': 'Draenei',
    'Ночные эльфы': 'Night Elf', 
    'Кровавые эльфы': 'Blood Elf',
    'Орки': 'Orc',
    'Люди': 'Human',
    'Нежить': 'Undead',
    'Таурены': 'Tauren',
    'Тролли': 'Troll',
    'Дворфы': 'Dwarf',
    'Гномы': 'Gnome'
}

# Эмодзи для визуального оформления
EMOJI = {
    'success': '✅',
    'error': '❌',
    'warning': '⚠️',
    'info': 'ℹ️',
    'database': '💾',
    'folder': '📂',
    'file': '📄',
    'time': '⏱️',
    'stats': '📊',
    'characters': '👤',
    'group': '👥',
    'thread': '🧵',
    'page': '📖',
    'playtime': '🎮',
    'name': '🏷️',
    'world': '🌍',
    'wizard': '🧙',
    'gear': '⚔️',
    'shield': '🛡️',
    'heart': '❤️',
    'fire': '🔥',
    'rocket': '🚀',
    'check': '✔️',
    'x': '✖️',
    'reload': '🔄',
    'search': '🔍',
    'download': '📥',
    'upload': '📤',
    'lock': '🔒',
    'unlock': '🔓',
    'bell': '🔔',
    'star': '⭐',
    'trophy': '🏆',
    'medal': '🏅',
    'crown': '👑',
    'flag': '🎌',
    'hourglass': '⌛',
    'stopwatch': '⏱️',
    'calendar': '📅',
    'clock': '🕒',
    'key': '🔑',
    'link': '🔗',
    'network': '🌐',
    'computer': '💻',
    'server': '🖥️',
    'storage': '🗄️',
    'book': '📚',
    'scroll': '📜',
    'memo': '📝',
    'pencil': '✏️',
    'hammer': '🔨',
    'wrench': '🔧',
    'magnify': '🔍',
    'chart': '📈',
    'progress': '📶',
    'dice': '🎲',
    'random': '🎲',
    'merge': '🔄'
}

# Глобальные переменные
global_stop_flag = False

# ==================== СИСТЕМА ЛОГГИРОВАНИЯ С ЦВЕТАМИ ====================

class EnhancedLogger:
    def __init__(self):
        self.logger = None
        self.console_buffer = StringIO()
        self.lock = threading.Lock()
        
    def setup(self, log_file):
        """Настройка расширенного логгера"""
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        self.logger = logging.getLogger('ezwow_parser')
        self.logger.setLevel(logging.INFO)
        
        # Форматтер с эмодзи
        formatter = logging.Formatter(
            '%(asctime)s %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Файловый обработчик
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        
        # Консольный обработчик с цветами
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        # Очистка и добавление обработчиков
        self.logger.handlers.clear()
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        self.logger.propagate = False
        
        # Перехват stdout/stderr
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        sys.stdout = self
        sys.stderr = self
    
    def write(self, message):
        """Перехват вывода в консоль"""
        with self.lock:
            self.original_stdout.write(message)
            self.console_buffer.write(message)
    
    def flush(self):
        self.original_stdout.flush()
        self.console_buffer.flush()
    
    def info(self, message, emoji="", color=""):
        """Информационное сообщение"""
        msg = self._format_message(message, emoji, color)
        with self.lock:
            self.logger.info(msg)
    
    def error(self, message, emoji="", color=""):
        """Сообщение об ошибке"""
        msg = self._format_message(message, emoji, color)
        with self.lock:
            self.logger.error(msg)
    
    def warning(self, message, emoji="", color=""):
        """Предупреждение"""
        msg = self._format_message(message, emoji, color)
        with self.lock:
            self.logger.warning(msg)
    
    def success(self, message, emoji=EMOJI['success']):
        """Сообщение об успехе"""
        msg = self._format_message(message, emoji, Fore.GREEN if COLORS_AVAILABLE else "")
        with self.lock:
            self.logger.info(msg)
    
    def debug(self, message, emoji="", color=""):
        """Отладочное сообщение"""
        msg = self._format_message(message, emoji, color)
        with self.lock:
            self.logger.debug(msg)
    
    def _format_message(self, message, emoji="", color=""):
        """Форматирование сообщения с эмодзи и цветом"""
        thread_name = threading.current_thread().name
        formatted_thread = f"[{Fore.CYAN if COLORS_AVAILABLE else ''}{thread_name}{Style.RESET_ALL if COLORS_AVAILABLE else ''}]"
        
        if emoji:
            message = f"{emoji} {message}"
        
        if color and COLORS_AVAILABLE:
            message = f"{color}{message}{Style.RESET_ALL}"
        
        return f"{formatted_thread} {message}"
    
    def save_console_log(self, filename):
        """Сохранение лога консоли"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(self.console_buffer.getvalue())
    
    def close(self):
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr

# Глобальный логгер
logger = EnhancedLogger()

# ==================== УТИЛИТЫ ====================

def get_session_id():
    """Генерация ID сессии"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def get_delay():
    """Получение задержки между запросами"""
    if CONFIG['RANDOM_DELAY']:
        return random.uniform(CONFIG['MIN_DELAY'], CONFIG['MAX_DELAY'])
    return CONFIG['DELAY_BETWEEN_REQUESTS']

def clean_text(element):
    """Очистка текста от лишних пробелов"""
    if not element:
        return ''
    text = element.get_text(strip=True)
    return re.sub(r'\s+', ' ', text).strip()

def extract_number(text, default=0):
    """Извлечение числа из текста, удаляя пробелы и нецифровые символы"""
    if not text:
        return default
    
    # Удаляем все пробелы
    text = text.replace(' ', '')
    
    # Извлекаем только цифры
    match = re.search(r'\d+', text)
    if match:
        try:
            return int(match.group())
        except (ValueError, TypeError):
            return default
    return default

def format_time(seconds):
    """Форматирование времени в читаемый вид"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m{secs:.0f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h{minutes:02d}m"

def format_time_hms(seconds):
    """Форматирование времени в ЧЧ:ММ:СС"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def print_banner():
    """Печать красивого баннера"""
    banner = f"""
{Fore.CYAN if COLORS_AVAILABLE else ''}{'='*70}
{EMOJI['world']} {Fore.YELLOW if COLORS_AVAILABLE else ''} ГИБРИДНЫЙ ПАРСЕР EZWOW {EMOJI['wizard']}
{Fore.CYAN if COLORS_AVAILABLE else ''}{'='*70}{Style.RESET_ALL if COLORS_AVAILABLE else ''}
"""
    print(banner)

def print_section(title, emoji=""):
    """Печать заголовка секции"""
    separator = f"{Fore.MAGENTA if COLORS_AVAILABLE else ''}{'─'*60}{Style.RESET_ALL if COLORS_AVAILABLE else ''}"
    title_text = f"{emoji} {Fore.YELLOW if COLORS_AVAILABLE else ''}{title}{Style.RESET_ALL if COLORS_AVAILABLE else ''}"
    print(f"\n{separator}")
    print(f"{title_text}")
    print(f"{separator}")

# ==================== БАЗЫ ДАННЫХ ====================

class ThreadDatabaseManager:
    """Менеджер базы данных для использования в отдельном потоке"""
    def __init__(self, tech_db_path, final_db_path):
        self.tech_db_path = tech_db_path
        self.final_db_path = final_db_path
        self.tech_conn = None
        self.final_conn = None
        
    def connect(self):
        """Создание соединений в текущем потоке"""
        if not self.tech_conn:
            self.tech_conn = sqlite3.connect(self.tech_db_path, check_same_thread=False)
            self.init_tech_tables()
        
        if not self.final_conn:
            self.final_conn = sqlite3.connect(self.final_db_path, check_same_thread=False)
            self.init_final_tables()
    
    def init_tech_tables(self):
        """Инициализация таблиц технической БД"""
        cursor = self.tech_conn.cursor()
        
        # Таблица для персонажей из playtime
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS playtime_data (
            playtime_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ez_id INTEGER UNIQUE,
            forum_name TEXT,
            name TEXT,
            level INTEGER,
            gs INTEGER,
            ilvl INTEGER,
            class TEXT,
            race TEXT,
            guild TEXT,
            kills INTEGER,
            ap INTEGER,
            pers_online BOOLEAN,
            forum_online BOOLEAN,
            st_value INTEGER,
            page_number INTEGER
        )
        """)
        
        # Таблица для персонажей из name
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS name_data (
            ez_id INTEGER PRIMARY KEY,
            forum_name TEXT,
            name TEXT,
            level INTEGER,
            gs INTEGER,
            ilvl INTEGER,
            class TEXT,
            race TEXT,
            guild TEXT,
            kills INTEGER,
            ap INTEGER,
            pers_online BOOLEAN,
            forum_online BOOLEAN,
            st_value INTEGER,
            page_number INTEGER
        )
        """)
        
        # Таблица прогресса
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS scan_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_type TEXT UNIQUE,
            last_processed_st INTEGER DEFAULT 0,
            last_st INTEGER DEFAULT 0,
            characters_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            last_update TEXT
        )
        """)
        
        self.tech_conn.commit()
    
    def init_final_tables(self):
        """Инициализация таблиц финальной БД"""
        cursor = self.final_conn.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS characters (
            ez_id INTEGER PRIMARY KEY,
            forum_name TEXT,
            name TEXT,
            level INTEGER,
            gs INTEGER,
            ilvl INTEGER,
            class TEXT,
            race TEXT,
            guild TEXT,
            kills INTEGER,
            ap INTEGER,
            pers_online BOOLEAN,
            forum_online BOOLEAN,
            source TEXT,
            scan_date TEXT
        )
        """)
        
        self.final_conn.commit()
    
    def save_characters_batch(self, characters, data_type, st_value, page_number):
        """Сохранение батча персонажей"""
        if not characters:
            return 0
        
        cursor = self.tech_conn.cursor()
        saved = 0
        
        try:
            if data_type == "playtime":
                for char_data in characters:
                    try:
                        char_data_with_page = char_data + (st_value, page_number)
                        cursor.execute("""
                        INSERT OR REPLACE INTO playtime_data
                        (ez_id, forum_name, name, level, gs, ilvl, class, race, guild, kills, ap, pers_online, forum_online, st_value, page_number)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, char_data_with_page)
                        saved += 1
                    except Exception as e:
                        logger.error(f"Ошибка сохранения персонажа {char_data[0]}: {str(e)}", emoji=EMOJI['error'])
            else:
                for char_data in characters:
                    try:
                        char_data_with_page = char_data + (st_value, page_number)
                        cursor.execute("""
                        INSERT OR REPLACE INTO name_data
                        (ez_id, forum_name, name, level, gs, ilvl, class, race, guild, kills, ap, pers_online, forum_online, st_value, page_number)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, char_data_with_page)
                        saved += 1
                    except Exception as e:
                        logger.error(f"Ошибка сохранения персонажа {char_data[0]}: {str(e)}", emoji=EMOJI['error'])
            
            self.tech_conn.commit()
            return saved
            
        except Exception as e:
            logger.error(f"Ошибка сохранения батча: {str(e)}", emoji=EMOJI['error'])
            self.tech_conn.rollback()
            return 0
    
    def save_progress(self, data_type, last_processed_st, last_st, char_count, status):
        """Сохранение прогресса сканирования"""
        try:
            cursor = self.tech_conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO scan_progress
            (data_type, last_processed_st, last_st, characters_count, status, last_update)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (data_type, last_processed_st, last_st, char_count, status, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            self.tech_conn.commit()
        except Exception as e:
            logger.error(f"Ошибка сохранения прогресса: {str(e)}", emoji=EMOJI['error'])
    
    def get_progress(self, data_type):
        """Получение прогресса сканирования"""
        try:
            cursor = self.tech_conn.cursor()
            cursor.execute("""
            SELECT last_processed_st, last_st, characters_count, status
            FROM scan_progress WHERE data_type = ?
            """, (data_type,))
            result = cursor.fetchone()
            
            if result:
                return {
                    'last_processed_st': result[0],
                    'last_st': result[1],
                    'char_count': result[2],
                    'status': result[3]
                }
            return {'last_processed_st': 0, 'last_st': 0, 'char_count': 0, 'status': 'active'}
        except Exception as e:
            logger.error(f"Ошибка получения прогресса: {str(e)}", emoji=EMOJI['error'])
            return {'last_processed_st': 0, 'last_st': 0, 'char_count': 0, 'status': 'active'}
    
    def close(self):
        """Закрытие соединений с БД"""
        if self.tech_conn:
            self.tech_conn.close()
        if self.final_conn:
            self.final_conn.close()

class MainDatabaseManager:
    """Менеджер базы данных для использования в основном потоке"""
    def __init__(self, session_id):
        self.session_id = session_id
        self.setup_folders()
    
    def setup_folders(self):
        """Создание необходимых папок"""
        os.makedirs(CONFIG['LOGS_FOLDER'], exist_ok=True)
        os.makedirs(CONFIG['BASES_FOLDER'], exist_ok=True)
    
    def init_tech_db(self):
        """Инициализация технической БД"""
        db_file = f"{CONFIG['BASES_FOLDER']}/tech_base_{self.session_id}.db"
        
        # Создаем соединение только для инициализации таблиц
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Таблица для персонажей из playtime
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS playtime_data (
            playtime_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ez_id INTEGER UNIQUE,
            forum_name TEXT,
            name TEXT,
            level INTEGER,
            gs INTEGER,
            ilvl INTEGER,
            class TEXT,
            race TEXT,
            guild TEXT,
            kills INTEGER,
            ap INTEGER,
            pers_online BOOLEAN,
            forum_online BOOLEAN,
            st_value INTEGER,
            page_number INTEGER
        )
        """)
        
        # Таблица для персонажей из name
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS name_data (
            ez_id INTEGER PRIMARY KEY,
            forum_name TEXT,
            name TEXT,
            level INTEGER,
            gs INTEGER,
            ilvl INTEGER,
            class TEXT,
            race TEXT,
            guild TEXT,
            kills INTEGER,
            ap INTEGER,
            pers_online BOOLEAN,
            forum_online BOOLEAN,
            st_value INTEGER,
            page_number INTEGER
        )
        """)
        
        # Таблица прогресса
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS scan_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_type TEXT UNIQUE,
            last_processed_st INTEGER DEFAULT 0,
            last_st INTEGER DEFAULT 0,
            characters_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            last_update TEXT
        )
        """)
        
        conn.commit()
        conn.close()
        
        logger.success(f"Техническая БД инициализирована: {db_file}", emoji=EMOJI['database'])
        return db_file
    
    def init_final_db(self):
        """Инициализация финальной БД"""
        db_file = f"{CONFIG['BASES_FOLDER']}/ezbase_final_{self.session_id}.db"
        
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS characters (
            ez_id INTEGER PRIMARY KEY,
            forum_name TEXT,
            name TEXT,
            level INTEGER,
            gs INTEGER,
            ilvl INTEGER,
            class TEXT,
            race TEXT,
            guild TEXT,
            kills INTEGER,
            ap INTEGER,
            pers_online BOOLEAN,
            forum_online BOOLEAN,
            source TEXT,
            scan_date TEXT
        )
        """)
        
        conn.commit()
        conn.close()
        
        logger.success(f"Финальная БД инициализирована: {db_file}", emoji=EMOJI['database'])
        return db_file
    
    def merge_to_final(self, tech_db_path, final_db_path):
        """Объединение данных в финальную БД"""
        print_section("ОБЪЕДИНЕНИЕ ДАННЫХ", EMOJI['merge'])
        logger.info("Начинаем объединение данных в финальную базу...", emoji=EMOJI['upload'])
        
        try:
            tech_conn = sqlite3.connect(tech_db_path)
            final_conn = sqlite3.connect(final_db_path)
            tech_cursor = tech_conn.cursor()
            final_cursor = final_conn.cursor()
            
            # Получаем статистику
            tech_cursor.execute("SELECT COUNT(*) FROM playtime_data")
            playtime_count = tech_cursor.fetchone()[0]
            tech_cursor.execute("SELECT COUNT(*) FROM name_data")
            name_count = tech_cursor.fetchone()[0]
            
            logger.info(f"Данные для объединения: {Fore.CYAN if COLORS_AVAILABLE else ''}Playtime - {playtime_count}{Style.RESET_ALL if COLORS_AVAILABLE else ''}, {Fore.CYAN if COLORS_AVAILABLE else ''}Name - {name_count}{Style.RESET_ALL if COLORS_AVAILABLE else ''}", emoji=EMOJI['stats'])
            
            if playtime_count == 0 and name_count == 0:
                logger.error("В технической базе нет данных для объединения!", emoji=EMOJI['error'])
                return 0
            
            scan_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            total_inserted = 0
            
            # Вставка данных из Playtime
            if playtime_count > 0:
                tech_cursor.execute("""
                SELECT ez_id, forum_name, name, level, gs, ilvl, class, race, guild, kills, ap, pers_online, forum_online
                FROM playtime_data
                """)
                playtime_chars = tech_cursor.fetchall()
                
                for char in playtime_chars:
                    try:
                        final_cursor.execute("""
                        INSERT OR REPLACE INTO characters
                        (ez_id, forum_name, name, level, gs, ilvl, class, race, guild, kills, ap, pers_online, forum_online, source, scan_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, char + ('playtime', scan_date))
                        total_inserted += 1
                    except Exception as e:
                        logger.error(f"Ошибка вставки персонажа {char[0]}: {str(e)}", emoji=EMOJI['error'])
                
                logger.success(f"Добавлено {len(playtime_chars)} персонажей из Playtime", emoji=EMOJI['playtime'])
            
            # Вставка данных из Name
            if name_count > 0:
                tech_cursor.execute("""
                SELECT ez_id, forum_name, name, level, gs, ilvl, class, race, guild, kills, ap, pers_online, forum_online
                FROM name_data
                """)
                name_chars = tech_cursor.fetchall()
                name_inserted = 0
                
                for char in name_chars:
                    try:
                        final_cursor.execute("SELECT ez_id FROM characters WHERE ez_id = ?", (char[0],))
                        if not final_cursor.fetchone():
                            final_cursor.execute("""
                            INSERT INTO characters
                            (ez_id, forum_name, name, level, gs, ilvl, class, race, guild, kills, ap, pers_online, forum_online, source, scan_date)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, char + ('name', scan_date))
                            total_inserted += 1
                            name_inserted += 1
                    except Exception as e:
                        logger.error(f"Ошибка вставки персонажа {char[0]}: {str(e)}", emoji=EMOJI['error'])
                
                logger.success(f"Добавлено {name_inserted} персонажей из Name", emoji=EMOJI['name'])
            
            # Финальная статистика
            final_cursor.execute("SELECT COUNT(*) FROM characters")
            total_final = final_cursor.fetchone()[0]
            
            final_conn.commit()
            tech_conn.close()
            final_conn.close()
            
            # Красивый вывод результатов
            print(f"\n{Fore.GREEN if COLORS_AVAILABLE else ''}{EMOJI['trophy']} РЕЗУЛЬТАТЫ ОБЪЕДИНЕНИЯ {EMOJI['trophy']}{Style.RESET_ALL if COLORS_AVAILABLE else ''}")
            print(f"{Fore.CYAN if COLORS_AVAILABLE else ''}{'═'*50}{Style.RESET_ALL if COLORS_AVAILABLE else ''}")
            print(f"{EMOJI['playtime']} Playtime: {Fore.YELLOW if COLORS_AVAILABLE else ''}{playtime_count}{Style.RESET_ALL if COLORS_AVAILABLE else ''} персонажей")
            print(f"{EMOJI['name']} Name: {Fore.YELLOW if COLORS_AVAILABLE else ''}{name_count}{Style.RESET_ALL if COLORS_AVAILABLE else ''} персонажей")
            print(f"{Fore.GREEN if COLORS_AVAILABLE else ''}{EMOJI['group']} Итого в финальной базе: {Fore.YELLOW if COLORS_AVAILABLE else ''}{total_final}{Style.RESET_ALL if COLORS_AVAILABLE else ''} персонажей{Style.RESET_ALL if COLORS_AVAILABLE else ''}")
            print(f"{Fore.CYAN if COLORS_AVAILABLE else ''}{'═'*50}{Style.RESET_ALL if COLORS_AVAILABLE else ''}")
            
            return total_final
            
        except Exception as e:
            logger.error(f"Ошибка при объединении баз: {str(e)}", emoji=EMOJI['error'])
            import traceback
            logger.error(f"Трассировка: {traceback.format_exc()}", emoji=EMOJI['error'])
            return 0

# ==================== ПАРСИНГ СТРАНИЦ ====================

def translate_class(class_name):
    """Перевод названия класса с русского на английский"""
    return CLASS_TRANSLATION.get(class_name, class_name)

def translate_race(race_name):
    """Перевод названия расы с русского на английский"""
    return RACE_TRANSLATION.get(race_name, race_name)

def parse_character(character):
    """Парсинг данных одного персонажа из HTML"""
    try:
        # Находим тег с именем персонажа
        name_td = character.find('td')
        if not name_td:
            return None
        
        name_tag = name_td.find('a')
        if not name_tag:
            return None
        
        # Извлекаем ID персонажа
        ez_id = None
        try:
            if 'character=' in str(name_tag):
                ez_id = int(str(name_tag).split('character=')[1].split('"')[0])
        except:
            # Альтернативный способ получения ID
            href = name_tag.get('href', '')
            if 'character=' in href:
                ez_id = int(href.split('character=')[1].split('&')[0])
        
        if not ez_id:
            return None
        
        # Форумное имя
        member_span = character.find('span', class_='member')
        forum_name = clean_text(member_span) if member_span else ''
        
        # Имя персонажа
        name = name_tag.get_text(strip=True)
        
        # Класс и раса
        race_icon = character.find('img', class_='character-icon character-race')
        class_icon = character.find('img', class_='character-icon character-class')
        
        original_race = race_icon['title'] if race_icon else ''
        original_class = class_icon['title'] if class_icon else ''
        race = translate_race(original_race)
        class_ = translate_class(original_class)
        
        # Гильдия
        guild_tag = character.find('span', class_='guild-name')
        guild = guild_tag.get_text(strip=True) if guild_tag else ''
        
        # Статистика - используем extract_number для обработки чисел с пробелами
        td_tags = character.find_all('td', class_='short')
        
        # Получаем текстовые значения
        level_text = clean_text(td_tags[0]) if len(td_tags) > 0 else '0'
        kills_text = clean_text(td_tags[1]) if len(td_tags) > 1 else '0'
        ilvl_text = clean_text(td_tags[2]) if len(td_tags) > 2 else '0'
        gs_text = clean_text(td_tags[3]) if len(td_tags) > 3 else '0'
        ap_text = clean_text(td_tags[4]) if len(td_tags) > 4 else '0'
        
        # Преобразуем в числа, удаляя пробелы
        level = extract_number(level_text, 0)
        kills = extract_number(kills_text, 0)
        ilvl = extract_number(ilvl_text, 0)
        gs = extract_number(gs_text, 0)
        ap = extract_number(ap_text, 0)
        
        # Проверка онлайн статуса персонажа
        character_icons = character.find('span', class_='character-icons')
        pers_online = False
        
        if character_icons:
            online_span = character_icons.find('span', class_='online')
            if online_span:
                online_img = online_span.find('img', title='В сети')
                pers_online = online_img is not None
        
        # Проверка онлайн статуса форумного аккаунта
        forum_acc_online = False
        if member_span:
            forum_online = member_span.find('span', class_='online')
            if forum_online:
                forum_img = forum_online.find('img', title='В сети')
                forum_acc_online = forum_img is not None
        
        return (
            ez_id,
            forum_name,
            name,
            level,
            gs,
            ilvl,
            class_,
            race,
            guild,
            kills,
            ap,
            pers_online,
            forum_acc_online
        )
        
    except Exception as e:
        logger.error(f"Ошибка парсинга персонажа: {str(e)}", emoji=EMOJI['error'])
        return None

def parse_html_content(html_content):
    """Парсинг HTML контента и извлечение персонажей"""
    try:
        soup = BeautifulSoup(html_content, 'lxml')
        characters = soup.find_all('tr', class_='character')
        parsed_characters = []
        
        for character in characters:
            char_data = parse_character(character)
            if char_data:
                parsed_characters.append(char_data)
                
        return parsed_characters, len(characters)
    except Exception as e:
        logger.error(f"Ошибка парсинга HTML: {str(e)}", emoji=EMOJI['error'])
        return [], 0

# ==================== СЕЛЕНИУМ МЕНЕДЖЕР ====================

class SeleniumManager:
    def __init__(self, thread_name):
        self.thread_name = thread_name
        self.driver = None
    
    def create_driver(self):
        """Создание драйвера для потока"""
        options = Options()
        options.headless = True
        
        # Оптимизации для скорости
        options.set_preference('permissions.default.image', 2)
        options.set_preference('javascript.enabled', True)
        options.set_preference('dom.ipc.plugins.enabled.libflashplayer.so', 'false')
        options.set_preference('app.update.enabled', False)
        
        try:
            if os.path.exists(CONFIG['FIREFOX_PROFILE_PATH']):
                profile = FirefoxProfile(CONFIG['FIREFOX_PROFILE_PATH'])
                options.profile = profile
                logger.info("Используется профиль Firefox", emoji=EMOJI['gear'])
        except Exception as e:
            logger.warning(f"Не удалось загрузить профиль: {str(e)}", emoji=EMOJI['warning'])
        
        try:
            self.driver = webdriver.Firefox(options=options)
            self.driver.set_page_load_timeout(CONFIG['MAX_WAIT_TIME'])
            
            # Убираем признаки автоматизации
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            return self.driver
            
        except Exception as e:
            logger.error(f"Ошибка создания драйвера: {str(e)}", emoji=EMOJI['error'])
            return None
    
    def get_page_html(self, url):
        """Получение страницы через Selenium"""
        if not self.driver:
            self.create_driver()
            if not self.driver:
                return None
        
        for attempt in range(CONFIG['MAX_RETRIES']):
            try:
                self.driver.get(url)
                
                # Ожидание загрузки
                WebDriverWait(self.driver, CONFIG['MAX_WAIT_TIME']).until(
                    lambda d: d.execute_script('return document.readyState') == 'complete'
                )
                
                # Проверка на блокировку
                page_source = self.driver.page_source.lower()
                if any(keyword in page_source for keyword in ['captcha', 'blocked', 'access denied']):
                    logger.warning("Обнаружена блокировка на странице", emoji=EMOJI['lock'])
                    time.sleep(5)
                    continue
                
                return self.driver.page_source
                
            except TimeoutException:
                if attempt < CONFIG['MAX_RETRIES'] - 1:
                    time.sleep(2)
                    
            except Exception as e:
                if attempt < CONFIG['MAX_RETRIES'] - 1:
                    time.sleep(2)
        
        return None
    
    def close(self):
        """Закрытие драйвера"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass

# ==================== СОХРАНЕНИЕ ФАЙЛОВ ====================

def save_page_to_file(html_content, save_dir, st_value, data_type, status="normal"):
    """Сохранение HTML страницы в файл"""
    if not CONFIG['SAVE_HTML_PAGES']:
        return None
    
    try:
        # Создаем папку для сохранения файлов
        os.makedirs(save_dir, exist_ok=True)
        
        # Рассчитываем номер страницы (начиная с 1)
        page_num = (st_value // CONFIG['STEP_SIZE']) + 1
        
        # Создаем имя файла
        if status == "blocked":
            filename = os.path.join(save_dir, f"page_{page_num:04d}_st_{st_value}_BLOCKED.html")
        else:
            filename = os.path.join(save_dir, f"page_{page_num:04d}_st_{st_value}.html")
        
        # Сохраняем HTML
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return filename
        
    except Exception as e:
        return None

# ==================== ОПРЕДЕЛЕНИЕ ДИАПАЗОНА ST ====================

def get_last_st():
    """Определение максимального значения st"""
    print_section("ОПРЕДЕЛЕНИЕ ДИАПАЗОНА", EMOJI['magnify'])
    logger.info("Определение максимального значения st...", emoji=EMOJI['search'])
    
    selenium_manager = SeleniumManager("range_detector")
    
    try:
        html = selenium_manager.get_page_html(LAST_PAGE_URL)
        if not html:
            logger.error("Не удалось определить последний st", emoji=EMOJI['error'])
            return 0
        
        # Парсим URL чтобы получить последний st
        soup = BeautifulSoup(html, 'lxml')
        
        # Пытаемся найти текущий URL разными способами
        current_url = None
        
        # Способ 1: Из мета-тега
        meta_url = soup.find('meta', {'property': 'og:url'})
        if meta_url and 'content' in meta_url.attrs:
            current_url = meta_url['content']
        
        # Способ 2: Из текущей страницы (Selenium)
        if not current_url and selenium_manager.driver:
            current_url = selenium_manager.driver.current_url
        
        if not current_url:
            logger.error("Не удалось получить текущий URL", emoji=EMOJI['error'])
            return 0
        
        # Извлекаем параметр st
        parsed_url = urlparse(current_url)
        query_params = parse_qs(parsed_url.query)
        
        if 'st' in query_params:
            last_st = int(query_params['st'][0])
            total_pages = (last_st // CONFIG['STEP_SIZE']) + 1
            
            logger.success(f"Определено: последний st={last_st}, всего страниц={total_pages}", emoji=EMOJI['check'])
            
            # Красивый вывод
            print(f"\n{Fore.GREEN if COLORS_AVAILABLE else ''}{EMOJI['stats']} ИНФОРМАЦИЯ О СКАНИРОВАНИИ:")
            print(f"{Fore.CYAN if COLORS_AVAILABLE else ''}{'─'*40}{Style.RESET_ALL if COLORS_AVAILABLE else ''}")
            print(f"{EMOJI['page']} Всего страниц: {Fore.YELLOW if COLORS_AVAILABLE else ''}{total_pages}{Style.RESET_ALL if COLORS_AVAILABLE else ''}")
            print(f"{EMOJI['link']} Последний st: {Fore.YELLOW if COLORS_AVAILABLE else ''}{last_st}{Style.RESET_ALL if COLORS_AVAILABLE else ''}")
            print(f"{EMOJI['gear']} Шаг пагинации: {Fore.YELLOW if COLORS_AVAILABLE else ''}{CONFIG['STEP_SIZE']}{Style.RESET_ALL if COLORS_AVAILABLE else ''}")
            print(f"{Fore.CYAN if COLORS_AVAILABLE else ''}{'─'*40}{Style.RESET_ALL if COLORS_AVAILABLE else ''}")
            
            return last_st
            
        else:
            logger.error("Не удалось найти параметр st в URL", emoji=EMOJI['error'])
            return 0
            
    except Exception as e:
        logger.error(f"Ошибка определения диапазона: {str(e)}", emoji=EMOJI['error'])
        return 0
        
    finally:
        selenium_manager.close()

# ==================== ОБРАБОТКА ПОТОКА ====================

def process_data_type(data_type, base_url, save_dir, tech_db_path, final_db_path, last_st):
    """Обработка одного типа данных (playtime или name)"""
    global global_stop_flag
    
    thread_name = threading.current_thread().name
    logger.info(f"Запуск обработки {data_type}...", emoji=EMOJI['thread'])
    
    # Создаем менеджер БД для этого потока
    db_manager = ThreadDatabaseManager(tech_db_path, final_db_path)
    db_manager.connect()
    
    # Создаем папку для сохранения файлов (только если нужно сохранять HTML)
    pages_dir = os.path.join(save_dir, data_type) if CONFIG['SAVE_HTML_PAGES'] else None
    
    # Инициализируем Selenium
    selenium_manager = SeleniumManager(thread_name)
    
    try:
        # Получаем прогресс
        progress = db_manager.get_progress(data_type)
        start_st = progress['last_processed_st']
        total_characters = progress['char_count']
        
        # Если в БД сохранен last_st и он отличается от текущего, используем меньший
        saved_last_st = progress['last_st']
        if saved_last_st > 0 and saved_last_st < last_st:
            last_st = saved_last_st
            logger.info(f"Используем сохраненный last_st: {last_st}", emoji=EMOJI['database'])
        
        if progress['status'] == 'completed':
            logger.info(f"Обработка {data_type} уже завершена ранее", emoji=EMOJI['check'])
            return total_characters
        
        logger.info(f"Начинаем с st={start_st}, последний st={last_st}", emoji=EMOJI['rocket'])
        
        # Рассчитываем количество страниц для прогресс-бара
        total_pages = (last_st // CONFIG['STEP_SIZE']) + 1
        start_page = (start_st // CONFIG['STEP_SIZE']) + 1
        
        # Статистика для прогресс-бара
        start_time_thread = time.time()
        page_times = []
        
        # Определяем эмодзи для типа данных
        data_type_emoji = EMOJI['playtime'] if data_type == "playtime" else EMOJI['name']
        
        # Создаем прогресс-бар с улучшенным форматом
        with tqdm(
            total=total_pages,
            initial=start_page - 1,
            desc=f"{data_type_emoji} {data_type:>10}",
            position=0 if data_type == "playtime" else 1,
            leave=False,
            bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]',
            dynamic_ncols=True
        ) as pbar:
            
            current_st = start_st
            current_page = start_page
            
            while current_st <= last_st and not global_stop_flag:
                page_start_time = time.time()
                
                # Формируем URL
                url = f"{base_url}{current_st}"
                
                # Скачиваем страницу
                html_content = selenium_manager.get_page_html(url)
                if not html_content:
                    logger.error(f"Не удалось скачать страницу {current_page} (st={current_st})", emoji=EMOJI['error'])
                    db_manager.save_progress(data_type, current_st, last_st, total_characters, 'error')
                    break
                
                # Сохраняем страницу в файл (только если SAVE_HTML_PAGES=True)
                if CONFIG['SAVE_HTML_PAGES']:
                    # Проверяем на блокировку
                    html_lower = html_content.lower()
                    is_blocked = any(keyword in html_lower for keyword in ['captcha', 'blocked', 'access denied'])
                    
                    status = "blocked" if is_blocked else "normal"
                    save_page_to_file(html_content, pages_dir, current_st, data_type, status)
                
                # Парсим страницу
                characters, char_count = parse_html_content(html_content)
                
                if char_count == 0:
                    logger.warning(f"На странице {current_page} (st={current_st}) нет персонажей!", emoji=EMOJI['warning'])
                else:
                    # Сохраняем в базу
                    saved_count = db_manager.save_characters_batch(characters, data_type, current_st, current_page)
                    if saved_count > 0:
                        total_characters += saved_count
                
                # Сохраняем прогресс
                db_manager.save_progress(data_type, current_st + CONFIG['STEP_SIZE'], last_st, total_characters, 'active')
                
                # Переходим к следующей странице
                current_st += CONFIG['STEP_SIZE']
                current_page += 1
                
                # Рассчитываем время обработки страницы
                page_time = time.time() - page_start_time
                page_times.append(page_time)
                
                # Рассчитываем среднее время на страницу
                avg_page_time = sum(page_times) / len(page_times) if page_times else 0
                
                # Рассчитываем оставшееся время
                remaining_pages = total_pages - (current_page - 1)
                est_remaining_time = remaining_pages * avg_page_time if avg_page_time > 0 else 0
                
                # Форматируем оставшееся время
                est_remaining_formatted = format_time_hms(est_remaining_time)
                
                # Обновляем прогресс-бар с краткой информацией
                pbar.set_postfix({
                    'avg': f"{avg_page_time:.1f}s",
                    'left': est_remaining_formatted,
                    'chars': total_characters
                })
                
                pbar.update(1)
                
                # Задержка между запросами
                delay = get_delay()
                if delay > 0:
                    time.sleep(delay)
        
        # Определяем статус завершения
        if current_st > last_st:
            status = 'completed'
            logger.success(f"Обработка {data_type} УСПЕШНО ЗАВЕРШЕНА", emoji=EMOJI['trophy'])
        else:
            status = 'stopped' if global_stop_flag else 'interrupted'
            logger.warning(f"Обработка {data_type} ПРЕРВАНА на st={current_st}", emoji=EMOJI['warning'])
        
        # Сохраняем финальный прогресс
        db_manager.save_progress(data_type, min(current_st, last_st), last_st, total_characters, status)
        
        return total_characters
        
    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}", emoji=EMOJI['error'])
        import traceback
        logger.error(f"Трассировка: {traceback.format_exc()}", emoji=EMOJI['error'])
        return 0
        
    finally:
        selenium_manager.close()
        db_manager.close()

# ==================== ОСНОВНОЙ ПРОЦЕСС ====================

def signal_handler(sig, frame):
    """Обработчик сигналов"""
    global global_stop_flag
    print(f"\n{Fore.YELLOW if COLORS_AVAILABLE else ''}{EMOJI['warning']} Получен сигнал прерывания...{Style.RESET_ALL if COLORS_AVAILABLE else ''}")
    logger.warning("Получен сигнал прерывания...", emoji=EMOJI['warning'])
    global_stop_flag = True

def print_config_summary():
    """Печать сводки конфигурации"""
    print_section("КОНФИГУРАЦИЯ", EMOJI['gear'])
    
    config_items = [
        (f"{EMOJI['playtime']} PLAYTIME_ONLY:", f"{'ДА' if CONFIG['PLAYTIME_ONLY'] else 'НЕТ'}"),
        (f"{EMOJI['file']} СОХРАНЕНИЕ HTML:", f"{'ДА' if CONFIG['SAVE_HTML_PAGES'] else 'НЕТ'}"),
        (f"{EMOJI['folder']} Папка сохранения:", f"{CONFIG['SAVE_DIR'] if CONFIG['SAVE_HTML_PAGES'] else 'НЕТ'}"),
        (f"{EMOJI['link']} Шаг пагинации:", f"{CONFIG['STEP_SIZE']}"),
        (f"{EMOJI['hourglass']} Макс. время ожидания:", f"{CONFIG['MAX_WAIT_TIME']}с"),
        (f"{EMOJI['reload']} Макс. попыток:", f"{CONFIG['MAX_RETRIES']}"),
        (f"{EMOJI['clock']} Задержка между запросами:", f"{CONFIG['DELAY_BETWEEN_REQUESTS']}с"),
        (f"{EMOJI['dice']} Случайная задержка:", f"{'ДА' if CONFIG['RANDOM_DELAY'] else 'НЕТ'}"),
    ]
    
    for item, value in config_items:
        print(f"{Fore.CYAN if COLORS_AVAILABLE else ''}{item:<30} {Fore.YELLOW if COLORS_AVAILABLE else ''}{value}{Style.RESET_ALL if COLORS_AVAILABLE else ''}")

def main():
    """Основная функция"""
    global global_stop_flag
    
    # Обработка сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Создаем уникальную папку для сессии
    session_id = get_session_id()
    CONFIG['SAVE_DIR'] = f"ezwow_scrape_{session_id}"
    
    # Создаем папку для сохранения файлов только если нужно
    if CONFIG['SAVE_HTML_PAGES']:
        os.makedirs(CONFIG['SAVE_DIR'], exist_ok=True)
    
    # Настройка логгера
    log_file = f"{CONFIG['LOGS_FOLDER']}/parser_{session_id}.log"
    logger.setup(log_file)
    
    # Печать красивого баннера
    print_banner()
    
    start_time = time.time()
    
    # Вывод информации о сессии
    print_section("ИНФОРМАЦИЯ О СЕССИИ", EMOJI['info'])
    
    session_info = [
        (f"{EMOJI['key']} Сессия:", session_id),
        (f"{EMOJI['calendar']} Дата:", date.today().strftime('%Y.%m.%d')),
        (f"{EMOJI['clock']} Время запуска:", datetime.now().strftime('%H:%M:%S')),
        (f"{EMOJI['computer']} PID:", os.getpid()),
    ]
    
    for item, value in session_info:
        print(f"{Fore.CYAN if COLORS_AVAILABLE else ''}{item:<20} {Fore.YELLOW if COLORS_AVAILABLE else ''}{value}{Style.RESET_ALL if COLORS_AVAILABLE else ''}")
    
    # Вывод конфигурации
    print_config_summary()
    
    try:
        # Инициализация базы данных в главном потоке
        print_section("ИНИЦИАЛИЗАЦИЯ БАЗ ДАННЫХ", EMOJI['database'])
        db_manager = MainDatabaseManager(session_id)
        tech_db_file = db_manager.init_tech_db()
        final_db_file = db_manager.init_final_db()
        
        # Определение максимального st
        last_st = get_last_st()
        if last_st == 0:
            logger.error("Не удалось определить максимальный st. Завершение.", emoji=EMOJI['error'])
            return
        
        # Рассчитываем количество страниц для отчета
        total_pages = (last_st // CONFIG['STEP_SIZE']) + 1
        logger.info(f"Будет обработано страниц: {total_pages} (st от 0 до {last_st} с шагом {CONFIG['STEP_SIZE']})", emoji=EMOJI['page'])
        
        # Запуск потоков
        print_section("ЗАПУСК ПОТОКОВ", EMOJI['thread'])
        threads = []
        results = {}
        
        # Поток для playtime
        playtime_thread = threading.Thread(
            target=lambda: results.update({'playtime': process_data_type(
                "playtime", PLAYTIME_URL, CONFIG['SAVE_DIR'], tech_db_file, final_db_file, last_st
            )}),
            name="Playtime_Thread"
        )
        threads.append(playtime_thread)
        
        # Поток для name (если нужно)
        if not CONFIG['PLAYTIME_ONLY']:
            name_thread = threading.Thread(
                target=lambda: results.update({'name': process_data_type(
                    "name", NAME_URL, CONFIG['SAVE_DIR'], tech_db_file, final_db_file, last_st
                )}),
                name="Name_Thread"
            )
            threads.append(name_thread)
        
        # Запуск потоков
        logger.info(f"Запуск {len(threads)} потоков...", emoji=EMOJI['rocket'])
        for i, thread in enumerate(threads):
            thread.start()
            logger.info(f"Поток {thread.name} запущен", emoji=EMOJI['check'])
            time.sleep(1)  # Задержка между запусками
        
        # Ожидание завершения
        for thread in threads:
            thread.join()
        
        # Объединение данных в финальную базу
        if not global_stop_flag:
            print_section("ОБЪЕДИНЕНИЕ ДАННЫХ", EMOJI['merge'])
            total_final = db_manager.merge_to_final(tech_db_file, final_db_file)
        else:
            logger.warning("Объединение данных пропущено из-за прерывания", emoji=EMOJI['warning'])
            total_final = 0
        
        # Статистика
        total_time = time.time() - start_time
        hours = int(total_time // 3600)
        minutes = int((total_time % 3600) // 60)
        seconds = int(total_time % 60)
        
        # Вычисляем среднюю производительность
        total_pages_processed = total_pages * (1 if CONFIG['PLAYTIME_ONLY'] else 2)
        avg_time_per_page = total_time / total_pages_processed if total_pages_processed > 0 else 0
        avg_chars_per_page = total_final / total_pages_processed if total_pages_processed > 0 else 0
        
        # Сохраняем консольный лог
        console_log_file = os.path.join(CONFIG['LOGS_FOLDER'], f"console_{session_id}.log")
        logger.save_console_log(console_log_file)
        
        # Итоговый отчет
        print_section("ИТОГОВЫЙ ОТЧЕТ", EMOJI['trophy'])
        
        # Красивый вывод статистики
        stats = [
            (f"{EMOJI['time']} Общее время:", f"{hours:02d}:{minutes:02d}:{seconds:02d}"),
            (f"{EMOJI['stats']} Страниц обработано:", f"{total_pages_processed}"),
            (f"{EMOJI['clock']} Среднее время на страницу:", f"{avg_time_per_page:.2f} сек"),
            (f"{EMOJI['characters']} Среднее персонажей на страницу:", f"{avg_chars_per_page:.1f}"),
            (f"{EMOJI['group']} Персонажей в базе:", f"{total_final}"),
            (f"{EMOJI['folder']} Папка с файлами:", f"{CONFIG['SAVE_DIR'] if CONFIG['SAVE_HTML_PAGES'] else 'НЕТ'}"),
            (f"{EMOJI['database']} Техническая база:", os.path.basename(tech_db_file)),
            (f"{EMOJI['database']} Финальная база:", os.path.basename(final_db_file)),
            (f"{EMOJI['memo']} Логи:", os.path.basename(log_file)),
        ]
        
        for item, value in stats:
            color = Fore.GREEN if 'Персонажей' in item else Fore.CYAN
            print(f"{color if COLORS_AVAILABLE else ''}{item:<35} {Fore.YELLOW if COLORS_AVAILABLE else ''}{value}{Style.RESET_ALL if COLORS_AVAILABLE else ''}")
        
        # Финальное сообщение
        print(f"\n{Fore.GREEN if COLORS_AVAILABLE else ''}{'═'*60}")
        print(f"{EMOJI['trophy']}  РАБОТА ЗАВЕРШЕНА УСПЕШНО!  {EMOJI['trophy']}")
        print(f"{'═'*60}{Style.RESET_ALL if COLORS_AVAILABLE else ''}\n")
        
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW if COLORS_AVAILABLE else ''}{EMOJI['warning']} Программа прервана пользователем{Style.RESET_ALL if COLORS_AVAILABLE else ''}")
        logger.warning("Программа прервана пользователем", emoji=EMOJI['warning'])
    except Exception as e:
        print(f"\n{Fore.RED if COLORS_AVAILABLE else ''}{EMOJI['error']} Критическая ошибка: {str(e)}{Style.RESET_ALL if COLORS_AVAILABLE else ''}")
        logger.error(f"Критическая ошибка: {str(e)}", emoji=EMOJI['error'])
        import traceback
        logger.error(f"Трассировка: {traceback.format_exc()}", emoji=EMOJI['error'])
    finally:
        logger.close()

if __name__ == "__main__":
    main()
