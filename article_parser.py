import requests
import feedparser
import json
from datetime import datetime
import time
import schedule
import random
import logging
import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client
from pathlib import Path

class ArticleParser:
    def __init__(self):
        # Настройка логирования
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('parser.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Загрузка конфигурации
        supabase_url, supabase_key = self._load_config()
        if not supabase_url or not supabase_key:
            self.logger.error("Не удалось загрузить конфигурацию Supabase")
            sys.exit(1)
            
        # Инициализация Supabase клиента
        self.supabase: Client = create_client(supabase_url, supabase_key)
        
        # Проверка и создание таблицы Links_articles, если она не существует
        self._ensure_table_exists()
        
        # Настройка запросов с ротацией User-Agent
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (iPad; CPU OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1'
        ]
        
        # Базовые заголовки
        self.headers = {
            'Accept': 'application/rss+xml, application/xml, application/atom+xml, application/json',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        
        # Расширенный список источников для парсинга
        self.blogs = [
            {
                'name': 'MIT Technology Review',
                'url': 'https://www.technologyreview.com/feed/',
                'type': 'rss',
                'category': 'AI'
            },
            {
                'name': 'Wired AI',
                'url': 'https://www.wired.com/feed/category/artificial-intelligence/rss',
                'type': 'rss',
                'category': 'AI'
            },
            {
                'name': 'TechTarget Enterprise AI',
                'url': 'https://www.techtarget.com/searchenterpriseai/rss',
                'type': 'rss',
                'category': 'AI',
                'parse_method': 'direct_request' # Специальный метод парсинга для сайтов с проблемными XML
            },
            {
                'name': 'The Verge AI',
                'url': 'https://www.theverge.com/rss/ai-artificial-intelligence/index.xml',
                'type': 'rss',
                'category': 'AI'
            },
            {
                'name': 'TechCrunch AI',
                'url': 'https://techcrunch.com/tag/ai/feed/',
                'type': 'rss',
                'category': 'AI'
            },
            {
                'name': 'Forbes AI',
                'url': 'https://www.forbes.com/innovation/ai/feed/',
                'type': 'rss',
                'category': 'AI'
            },
            {
                'name': 'ZDNet AI',
                'url': 'https://www.zdnet.com/topic/artificial-intelligence/rss.xml',
                'type': 'rss',
                'category': 'AI'
            }
        ]

        # Расширенный список ключевых слов для ИИ
        self.ai_keywords = [
            'artificial intelligence', 'ai', 'machine learning', 'ml',
            'neural network', 'deep learning', 'gpt', 'llm', 
            'chatbot', 'robotics', 'computer vision', 'nlp',
            'natural language processing', 'transformers', 'large language model',
            'reinforcement learning', 'autonomous systems', 'ai ethics',
            'artificial general intelligence', 'agi', 'machine intelligence',
            'neural networks', 'deep neural networks', 'ai model',
            'language model', 'ai research', 'ai development',
            'ai applications', 'ai technology', 'ai solutions',
            'ai tools', 'ai software', 'ai platform',
            'ai startup', 'ai company', 'ai industry'
        ]

    def _load_config(self):
        """Безопасная загрузка конфигурации"""
        # Пробуем загрузить из .env файла
        env_path = Path('.') / '.env'
        load_dotenv(dotenv_path=env_path)
        
        # Проверяем переменные окружения
        supabase_url = os.environ.get('SUPABASE_URL')
        supabase_key = os.environ.get('SUPABASE_KEY')
        
        # Если переменных нет, пробуем загрузить из конфиг файла
        if not supabase_url or not supabase_key:
            try:
                config_path = Path('.') / 'config.json'
                if config_path.exists():
                    with open(config_path, 'r') as f:
                        config = json.load(f)
                        supabase_url = config.get('SUPABASE_URL')
                        supabase_key = config.get('SUPABASE_KEY')
            except Exception as e:
                self.logger.error(f"Ошибка загрузки конфигурации: {str(e)}")
        
        return supabase_url, supabase_key

    def _ensure_table_exists(self):
        """Проверка и создание таблицы Links_articles, если она не существует"""
        try:
            # Проверяем существование таблицы, выполняя простой запрос
            try:
                self.supabase.table('Links_articles').select('id').limit(1).execute()
                self.logger.info("Таблица Links_articles уже существует")
            except Exception as e:
                self.logger.error(f"Ошибка при проверке таблицы: {str(e)}")
                self.logger.info("Создание таблицы Links_articles...")
                
                # Создаем таблицу через SQL запрос
                sql = """
                CREATE TABLE IF NOT EXISTS "Links_articles" (
                    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
                    url TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    source TEXT NOT NULL,
                    category TEXT,
                    summary TEXT,
                    published_date TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    status TEXT DEFAULT 'new'
                );
                
                -- Создаем индексы для ускорения поиска
                CREATE INDEX IF NOT EXISTS idx_links_articles_url ON "Links_articles" (url);
                CREATE INDEX IF NOT EXISTS idx_links_articles_source ON "Links_articles" (source);
                CREATE INDEX IF NOT EXISTS idx_links_articles_category ON "Links_articles" (category);
                """
                
                # Выполняем SQL через Supabase
                response = self.supabase.rpc('exec_sql', {'sql': sql}).execute()
                
                if hasattr(response, 'error') and response.error:
                    self.logger.error(f"Ошибка создания таблицы: {response.error}")
                    self.logger.warning("Не удалось создать таблицу автоматически. Пожалуйста, создайте таблицу вручную через интерфейс Supabase.")
                else:
                    self.logger.info("Таблица Links_articles успешно создана")
        except Exception as e:
            self.logger.error(f"Ошибка при проверке/создании таблицы: {str(e)}")
            self.logger.warning("Пожалуйста, создайте таблицу вручную через интерфейс Supabase со следующей структурой:")
            self.logger.warning("""
            CREATE TABLE "Links_articles" (
                id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
                url TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                source TEXT NOT NULL,
                category TEXT,
                summary TEXT,
                published_date TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                status TEXT DEFAULT 'new'
            );
            CREATE INDEX idx_links_articles_url ON "Links_articles" (url);
            """)

    def _get_random_user_agent(self):
        """Получение случайного User-Agent"""
        return random.choice(self.user_agents)
        
    def is_ai_related(self, entry):
        """Проверка, относится ли статья к тематике ИИ по ключевым словам"""
        if not entry:
            return False
            
        # Проверяем заголовок
        title = entry.get('title', '').lower()
        
        # Проверяем описание/содержимое
        description = entry.get('description', '').lower()
        summary = entry.get('summary', '').lower()
        content = ''
        
        # Пытаемся получить содержимое из разных возможных структур RSS
        if 'content' in entry:
            try:
                if isinstance(entry['content'], list):
                    content = entry['content'][0].get('value', '').lower()
                else:
                    content = str(entry['content']).lower()
            except:
                pass
                
        # Объединяем все тексты для поиска
        all_text = title + ' ' + description + ' ' + summary + ' ' + content
        
        # Проверяем наличие ключевых слов
        return any(keyword in all_text for keyword in self.ai_keywords)

    def parse_rss_feed(self, blog_config):
        """Парсинг RSS фида с учетом различных вариантов структуры"""
        self.logger.info(f"Загрузка RSS фида {blog_config['name']}")
        
        # Если задан специальный метод парсинга, используем его
        if blog_config.get('parse_method') == 'direct_request':
            return self._parse_with_direct_request(blog_config, self.headers.copy())
            
        # Обычный парсинг через feedparser
        try:
            # Подготовка заголовков с случайным User-Agent
            headers = self.headers.copy()
            headers['User-Agent'] = self._get_random_user_agent()
            
            # Для надежности делаем HTTP-запрос вручную, а затем передаем ответ в feedparser
            response = requests.get(blog_config['url'], headers=headers, timeout=20)
            response.raise_for_status()  # Проверка на ошибки HTTP
            
            # Парсинг RSS с помощью feedparser
            feed = feedparser.parse(response.content)
            
            if feed.bozo and not isinstance(feed.bozo_exception, (feedparser.ThingsNobodyCaresAboutButMe, TypeError)):
                # Есть ошибка в XML структуре
                self.logger.error(f"Ошибка парсинга фида {blog_config['name']}: {feed.bozo_exception}")
                return []
                
            # Проверяем на пустой фид или ошибки
            if not hasattr(feed, 'entries') or not feed.entries:
                self.logger.warning(f"Пустой фид или ошибка структуры: {blog_config['name']}")
                return []
                
            articles = []
            
            # Обрабатываем все записи из фида
            for entry in feed.entries:
                # Для AI-категории проверяем, относится ли статья к тематике ИИ
                if blog_config.get('category') == 'AI' and not self.is_ai_related(entry):
                    continue
                    
                # Формируем данные статьи
                title = entry.get('title', '')
                link = entry.get('link', '')
                
                # Проверка обязательных полей
                if not title or not link:
                    continue
                    
                # Получаем описание или содержимое
                summary = ''
                if hasattr(entry, 'summary'):
                    summary = entry.summary
                elif hasattr(entry, 'description'):
                    summary = entry.description
                    
                # Получаем дату публикации
                published = entry.get('published', '')
                if not published:
                    published = entry.get('updated', '')
                    
                # Создаем запись статьи
                article = {
                    'title': title,
                    'url': link,
                    'source': blog_config['name'],
                    'category': blog_config.get('category', ''),
                    'summary': summary,
                    'published_date': published
                }
                
                articles.append(article)
                self.logger.info(f"Найдена статья: {title}")
                
            return articles
        except Exception as e:
            self.logger.error(f"Ошибка при парсинге {blog_config['name']}: {str(e)}")
            return []

    def _parse_with_direct_request(self, blog_config, headers):
        """Специальный метод парсинга для сайтов с проблемными XML"""
        try:
            # Добавляем случайный User-Agent
            headers['User-Agent'] = self._get_random_user_agent()
            
            # Делаем запрос напрямую
            response = requests.get(blog_config['url'], headers=headers, timeout=20)
            response.raise_for_status()
            
            # Пытаемся сначала обработать как обычный XML
            try:
                feed = feedparser.parse(response.content)
                
                if not hasattr(feed, 'entries') or not feed.entries or (feed.bozo and not isinstance(feed.bozo_exception, (feedparser.ThingsNobodyCaresAboutButMe, TypeError))):
                    # Если есть ошибка в XML, пробуем обработать контент вручную
                    raise Exception("Invalid XML, trying to parse manually")
                    
                # Если успешно распарсили через feedparser, используем стандартный метод
                return self.parse_rss_feed({**blog_config, 'parse_method': None})
                    
            except Exception as xml_error:
                self.logger.warning(f"Стандартный парсинг не удался для {blog_config['name']}, пробуем ручной парсинг: {str(xml_error)}")
                
                # Получаем текст и пытаемся найти элементы RSS вручную
                content = response.text
                
                # Простой алгоритм извлечения элементов из XML
                articles = []
                items = content.split('<item')
                
                for item in items[1:]:  # Пропускаем первый элемент (заголовок)
                    try:
                        # Извлекаем основные поля
                        title_match = re.search(r'<title[^>]*>(.*?)</title>', item, re.DOTALL)
                        link_match = re.search(r'<link[^>]*>(.*?)</link>', item, re.DOTALL)
                        description_match = re.search(r'<description[^>]*>(.*?)</description>', item, re.DOTALL)
                        date_match = re.search(r'<pubDate[^>]*>(.*?)</pubDate>', item, re.DOTALL)
                        
                        if title_match and link_match:
                            title = title_match.group(1).strip()
                            link = link_match.group(1).strip()
                            
                            # Очищаем от CDATA и экранирования
                            title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', title)
                            link = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', link)
                            
                            # Создаем описание если есть
                            summary = ''
                            if description_match:
                                summary = description_match.group(1).strip()
                                summary = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', summary)
                                
                            # Дата публикации если есть
                            published = ''
                            if date_match:
                                published = date_match.group(1).strip()
                                
                            # Проверяем на тематику ИИ, если нужно
                            is_ai = True
                            if blog_config.get('category') == 'AI':
                                all_text = (title + ' ' + summary).lower()
                                is_ai = any(keyword in all_text for keyword in self.ai_keywords)
                                
                            if is_ai:
                                article = {
                                    'title': title,
                                    'url': link,
                                    'source': blog_config['name'],
                                    'category': blog_config.get('category', ''),
                                    'summary': summary,
                                    'published_date': published
                                }
                                
                                articles.append(article)
                                self.logger.info(f"Найдена статья: {title}")
                    except Exception as item_error:
                        self.logger.error(f"Ошибка при парсинге элемента: {str(item_error)}")
                        continue
                        
                return articles
                
        except Exception as e:
            self.logger.error(f"Ошибка при прямом парсинге {blog_config['name']}: {str(e)}")
            return []

    def save_to_supabase(self, article_data):
        """Сохранение статьи в Supabase с проверкой на дубликаты"""
        try:
            # Проверяем наличие статьи по URL (чтобы избежать дубликатов)
            check_response = self.supabase.table('Links_articles').select('url').eq('url', article_data['url']).execute()
            
            if check_response.data:
                # Статья уже есть в базе
                return False
                
            # Добавляем статью в базу
            insert_response = self.supabase.table('Links_articles').insert(article_data).execute()
            
            if hasattr(insert_response, 'error') and insert_response.error:
                self.logger.error(f"Ошибка добавления статьи в Supabase: {insert_response.error}")
                return False
                
            self.logger.info(f"Статья добавлена в Supabase: {article_data['title']}")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении в Supabase: {str(e)}")
            return False

    def process_articles(self):
        """Обработка статей из всех источников"""
        start_time = datetime.now()
        self.logger.info(f"Начало проверки в {start_time.isoformat()}")
        
        # Обрабатываем все источники
        for blog in self.blogs:
            try:
                self.logger.info(f"Обработка {blog['name']}...")
                
                # Парсим RSS фид
                articles = self.parse_rss_feed(blog)
                
                # Сохраняем статьи в Supabase
                for article in articles:
                    self.save_to_supabase(article)
                    
                # Задержка между обработкой источников
                time.sleep(2)
            except Exception as e:
                self.logger.error(f"Ошибка при обработке {blog['name']}: {str(e)}")
                
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        self.logger.info(f"Проверка завершена за {duration:.2f} секунд")

    def run_scheduled(self, interval_minutes=60):
        """Запуск периодической проверки"""
        self.logger.info(f"Запуск периодической проверки каждые {interval_minutes} минут")
        
        # Немедленно запускаем первую проверку
        self.process_articles()
        
        # Планируем следующие проверки
        schedule.every(interval_minutes).minutes.do(self.process_articles)
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(5)
        except KeyboardInterrupt:
            self.logger.info("Периодическая проверка остановлена пользователем")
        except Exception as e:
            self.logger.error(f"Ошибка в периодической проверке: {str(e)}")
            raise

def main():
    """Основная функция запуска парсера"""
    parser = ArticleParser()
    
    if len(sys.argv) > 1 and sys.argv[1] == "once":
        # Однократный запуск
        parser.process_articles()
    else:
        # Периодический запуск (по умолчанию)
        parser.run_scheduled()

if __name__ == "__main__":
    main()