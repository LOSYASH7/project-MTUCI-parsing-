import requests
from bs4 import BeautifulSoup
import sqlite3
from urllib.parse import urljoin

# Функция для парсинга вакансий со всех страниц по заданному запросу

# Функция для парсинга вакансий со всех страниц по заданному запросу
def parse_all_pages(base_url, query):
    page_number = 1
    vacancies_data = []
    while True:
        url = f"{base_url}/vacancies?type=all&page={page_number}&q={query}"
        response = requests.get( url )
        if response.status_code != 200:
            print( f"Failed to retrieve data from page {page_number}" )
            break
        soup = BeautifulSoup( response.text, 'html.parser' )
        vacancies = soup.find_all( 'div', class_='vacancy-card' )
        if len( vacancies ) == 0:
            break
        for vacancy in vacancies:
            title_element = vacancy.find( 'div', class_='vacancy-card__title' )
            company_element = vacancy.find( 'div', class_='vacancy-card__company' )
            skills_element = vacancy.find( 'div', class_='vacancy-card__skills' )
            link_element = vacancy.find( 'a', class_='vacancy-card__title-link' )
            title = title_element.text.strip() if title_element else 'N/A'
            company = company_element.text.strip() if company_element else 'N/A'
            skills = skills_element.text.strip() if skills_element else 'N/A'
            link = urljoin( base_url, link_element['href'] ) if link_element else '#'
            vacancies_data.append( {
                'title': title,
                'company': company,
                'skills': skills,
                'link': link
            } )
        page_number += 1
    return vacancies_data


# Создаем таблицу, если она еще не существует
def create_or_update_table():
    conn = sqlite3.connect( 'vacancies.db' )
    cursor = conn.cursor()
    cursor.execute( '''
        CREATE TABLE IF NOT EXISTS parsed_vacancies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            company TEXT,
            skills TEXT,
            link TEXT UNIQUE,
            parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''' )
    conn.commit()
    conn.close()


# Функция для вставки или обновления вакансий в базу данных
def insert_or_update_vacancies_to_db(vacancies):
    conn = sqlite3.connect( 'vacancies.db' )
    cursor = conn.cursor()
    for vacancy in vacancies:
        cursor.execute( '''
            INSERT OR IGNORE INTO parsed_vacancies (title, company, skills, link)
            VALUES (?, ?, ?, ?)
        ''', (vacancy['title'], vacancy['company'], vacancy['skills'], vacancy['link']) )

        # Если запись уже существует, обновляем ее
        cursor.execute( '''
            UPDATE parsed_vacancies
            SET title = ?, company = ?, skills = ?, parsed_at = CURRENT_TIMESTAMP
            WHERE link = ?
        ''', (vacancy['title'], vacancy['company'], vacancy['skills'], vacancy['link']) )

    conn.commit()
    conn.close()


# Пример использования функций
if __name__ == "__main__":
    base_url = "https://example.com"  # Замените на фактический URL
    query = "developer"

    create_or_update_table()


# Функция для вставки вакансий в базу данных только если их там ещё нет
def insert_vacancies_to_db(vacancies):
    conn = sqlite3.connect('vacancies.db')
    cursor = conn.cursor()
    for vacancy in vacancies:
        cursor.execute('''
            SELECT id FROM parsed_vacancies WHERE title = ? AND company = ?
        ''', (vacancy['title'], vacancy['company']))
        existing_vacancy = cursor.fetchone()
        if existing_vacancy is None:
            cursor.execute('''
            INSERT INTO parsed_vacancies (title, company, skills, link)
            VALUES (?, ?, ?, ?)
            ''', (vacancy['title'], vacancy['company'], vacancy['skills'], vacancy['link']))
    conn.commit()
    conn.close()

# Функция для получения последних вакансий из базы данных
def get_last_vacancies():
    conn = sqlite3.connect('vacancies.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT title, company, skills, link, parsed_at
        FROM parsed_vacancies
        ORDER BY parsed_at DESC
    ''')
    vacancies = cursor.fetchall()
    conn.close()

    formatted_vacancies = []
    for vacancy in vacancies:
        formatted_vacancy = f"Title: {vacancy[0]}\nCompany: {vacancy[1]}\nSkills: {vacancy[2]}\nLink: {vacancy[3]}\nParsed At:{vacancy[4]}\n"
        formatted_vacancies.append(formatted_vacancy)

    return "\n\n".join(formatted_vacancies)



# Основная логика парсинга
if __name__ == "__main__":
    # Указываем запрос для поиска вакансий
    query = "Python Developer"

    # Парсим данные вакансий
    base_url = "https://career.habr.com"
    all_vacancies_data = parse_all_pages(base_url, query)

    # Вставляем данные в базу данных
    insert_vacancies_to_db(all_vacancies_data)

    # Получаем и выводим последние вакансии
    print(get_last_vacancies())