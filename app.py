from flask import Flask, render_template, request, g
import requests
from bs4 import BeautifulSoup
import sqlite3
from urllib.parse import urljoin
from datetime import datetime

app = Flask(__name__)
DATABASE = 'vacancies.db'


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def create_table_if_not_exists():
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parsed_vacancies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            company TEXT,
            skills TEXT,
            link TEXT UNIQUE,
            parsed_at TEXT
        )
    ''')
    db.commit()

def add_parsed_at_column():
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute('SELECT parsed_at FROM parsed_vacancies LIMIT 1')
    except sqlite3.OperationalError:
        cursor.execute('ALTER TABLE parsed_vacancies ADD COLUMN parsed_at TEXT')
        cursor.execute('UPDATE parsed_vacancies SET parsed_at = ?', (datetime.now().isoformat(),))
    db.commit()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/advanced_search', methods=['POST'])
def advanced_search():
    city = request.form.get('city')
    company = request.form.get('company')
    job_title = request.form.get('job_title')
    skills = request.form.get('skills')

    vacancies = parse_vacancies(city, company, job_title, skills)

    return render_template('results.html', vacancies=vacancies)


@app.route('/retry_search', methods=['POST'])
def retry_search():
    city = request.form.get('city')
    company = request.form.get('company')
    job_title = request.form.get('job_title')
    skills = request.form.get('skills')

    vacancies = filter_vacancies(city, company, job_title, skills)

    return render_template('results.html', vacancies=vacancies)


@app.route('/latest_vacancies')
def latest_vacancies():
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        'SELECT title, company, skills, link, parsed_at FROM parsed_vacancies ORDER BY parsed_at DESC LIMIT 10')
    latest_vacancies = cursor.fetchall()
    return render_template('latest_vacancies.html', vacancies=latest_vacancies)


@app.route('/parsing_analysis')
def parsing_analysis():
    db = get_db()
    cursor = db.cursor()

    # Получаем параметры из строки запроса
    company_filter = request.args.get('company')
    title_filter = request.args.get('title')

    # Отладочный вывод
    print(f"Company filter: {company_filter}")
    print(f"Title filter: {title_filter}")

    # Формируем запрос для компаний
    company_where_clauses = []
    company_params = {}
    if company_filter:
        company_where_clauses.append("company = :company")
        company_params['company'] = company_filter
    if title_filter:
        company_where_clauses.append("title = :title")
        company_params['title'] = title_filter

    company_query = "SELECT COUNT(*), company FROM parsed_vacancies"
    if company_where_clauses:
        company_query += " WHERE " + " AND ".join(company_where_clauses)
    company_query += " GROUP BY company"
    print(f"Executing company query: {company_query} with params: {company_params}")
    cursor.execute(company_query, company_params)
    company_count = cursor.fetchall()
    print(f"Company count: {company_count}")  # Отладка

    # Формируем запрос для должностей
    title_where_clauses = []
    title_params = {}
    if company_filter:
        title_where_clauses.append("company = :company")
        title_params['company'] = company_filter
    if title_filter:
        title_where_clauses.append("title = :title")
        title_params['title'] = title_filter

    title_query = "SELECT COUNT(*), title FROM parsed_vacancies"
    if title_where_clauses:
        title_query += " WHERE " + " AND ".join(title_where_clauses)
    title_query += " GROUP BY title"
    print(f"Executing title query: {title_query} with params: {title_params}")
    cursor.execute(title_query, title_params)
    job_count = cursor.fetchall()
    print(f"Job count: {job_count}")  # Отладка

    # Формируем запрос для общего количества
    total_where_clauses = []
    total_params = {}
    if company_filter:
        total_where_clauses.append("company = :company")
        total_params['company'] = company_filter
    if title_filter:
        total_where_clauses.append("title = :title")
        total_params['title'] = title_filter

    total_query = "SELECT COUNT(*) FROM parsed_vacancies"
    if total_where_clauses:
        total_query += " WHERE " + " AND ".join(total_where_clauses)
    print(f"Executing total query: {total_query} with params: {total_params}")
    cursor.execute(total_query, total_params)
    total_found = cursor.fetchone()[0]
    print(f"Total found: {total_found}")  # Отладка

    return render_template('parsing_analysis.html', company_count=company_count, job_count=job_count, total_found=total_found)


def get_all_vacancies():
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT title, company, skills, link, parsed_at FROM parsed_vacancies')
    all_vacancies = cursor.fetchall()
    return all_vacancies


def build_query_string(city, company, job_title, skills):
    query_parts = []
    if job_title:
        query_parts.append(job_title)
    if skills:
        query_parts.append(skills)
    if city:
        query_parts.append(city)
    if company:
        query_parts.append(company)
    return "+".join(query_parts)


def parse_vacancies(city, company, job_title, skills):
    query_string = build_query_string(city, company, job_title, skills)

    db = get_db()
    cursor = db.cursor()

    # Очистка таблицы перед добавлением новых данных
    cursor.execute("DELETE FROM parsed_vacancies")
    db.commit()

    vacancies_data = []
    page = 1
    while True:
        url = f"https://career.habr.com/vacancies?type=all&page={page}&q={query_string}"
        response = requests.get( url )
        if response.status_code != 200:
            break
        soup = BeautifulSoup( response.text, 'html.parser' )
        vacancies = soup.find_all( 'div', class_='vacancy-card' )
        if not vacancies:
            break
        for vacancy in vacancies:
            title_element = vacancy.find( 'div', class_='vacancy-card__title' )
            company_element = vacancy.find( 'div', class_='vacancy-card__company' )
            skills_element = vacancy.find( 'div', class_='vacancy-card__skills' )
            link_element = title_element.find( 'a', href=True )
            title = title_element.text.strip() if title_element else 'N/A'
            company = company_element.text.strip() if company_element else 'N/A'
            skills = skills_element.text.strip() if skills_element else 'N/A'
            link = urljoin( "https://career.habr.com", link_element['href'] ) if link_element else '#'
            vacancies_data.append( {
                'title': title,
                'company': company,
                'skills': skills,
                'link': link
            } )
        page += 1

    # Добавление новых записей в базу данных
    cursor.executemany(
        'INSERT INTO parsed_vacancies (title, company, skills, link, parsed_at) VALUES (?, ?, ?, ?, ?)',
        [(v['title'], v['company'], v['skills'], v['link'], datetime.now().isoformat()) for v in vacancies_data]
    )
    db.commit()

    return vacancies_data
def filter_vacancies(city=None, company=None, job_title=None, skills=None):
    db = get_db()
    cursor = db.cursor()
    query = "SELECT title, company, skills, link, parsed_at FROM parsed_vacancies WHERE 1=1"
    params = []

    if city:
        query += " AND title LIKE ?"
        params.append(f"%{city}%")
    if company:
        query += " AND company LIKE ?"
        params.append(f"%{company}%")
    if job_title:
        query += " AND title LIKE ?"
        params.append(f"%{job_title}%")
    if skills:
        query += " AND skills LIKE ?"
        params.append(f"%{skills}%")

    cursor.execute(query, params)
    results = cursor.fetchall()

    return results


if __name__ == '__main__':
    with app.app_context():
        create_table_if_not_exists()
        add_parsed_at_column()
    app.run(debug=True)