
from flask import Flask, render_template_string
import sqlite3
import os

app = Flask(__name__)

# Путь к нашей базе данных
DATABASE = os.path.join(os.path.dirname(__file__), "requests.db")


# Получаем заявки из базы данных
def get_requests():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()
    cursor.execute("""
        SELECT r.id, r.title, r.description, s.name AS status, c.name AS category
        FROM Requests r
        JOIN Statuses s ON s.id = r.status_id
        JOIN Categories c ON c.id = r.category_id
        ORDER BY r.id
    """)

    requests = cursor.fetchall()
    connection.close()

    return requests


# Главная страница сайта
@app.route("/")
def home():
    requests = get_requests()

    html = """
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Система учёта заявок</title>
        <style>
            body {
                font-family: Arial;
                background: #f3f4f6;
                padding: 30px;
            }

            h1 {
                color: #26354a;
            }

            table {
                width: 100%;
                border-collapse: collapse;
                background: white;
            }

            th, td {
                padding: 12px;
                border: 1px solid #ddd;
                text-align: left;
            }

            th {
                background: #26354a;
                color: white;
            }
        </style>
    </head>

    <body>
        <h1>Система учёта заявок</h1>
        <h2>Список заявок</h2>

        <table>
            <tr>
                <th>ID</th>
                <th>Название</th>
                <th>Описание</th>
                <th>Статус</th>
            </tr>

            {% for request in requests %}
            <tr>
                <td>{{ request[0] }}</td>
                <td>{{ request[1] }}</td>
                <td>{{ request[2] }}</td>
                <td>{{ request[3] }}</td>
            </tr>
            {% endfor %}
        </table>
    </body>
    </html>
    """

    return render_template_string(html, requests=requests)


if __name__ == "__main__":
    app.run(debug=True)
