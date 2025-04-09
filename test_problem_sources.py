#!/usr/bin/env python3
import sys
import os
from article_parser import ArticleParser

# Создаем экземпляр парсера
parser = ArticleParser()

# Тестируем только проблемные источники
problem_sources = [src for src in parser.blogs if src['name'] in ['TechTarget Enterprise AI', 'Forbes AI']]

print(f'Тестирование {len(problem_sources)} проблемных источников:')
for source in problem_sources:
    print(f'\nПроверка {source["name"]}...')
    articles = parser.parse_rss_feed(source)
    print(f'Найдено статей: {len(articles)}')
    for article in articles[:3]:  # Показываем только первые 3 статьи
        print(f' - {article["title"]}')