from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from config import SQLALCHEMY_DATABASE_URI, SQLALCHEMY_TRACK_MODIFICATIONS, SECRET_KEY
from extensions import db, migrate
from models import *

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS
app.config['SECRET_KEY'] = SECRET_KEY

db.init_app(app)
migrate.init_app(app, db)

@app.route('/', methods=['GET', 'POST'])
def login():
    if 'login_flash' in session:
        category, message = session['login_flash']
        flash(message, category)
        session.pop('login_flash')

    if request.method == 'POST':
        login = request.form['login']
        password = request.form['password']

        account = Account.query.filter_by(login=login).first()

        if account:
            if account.check_password(password):
                return 'Успіх'
        else:
            session['login_flash'] = ('error', 'Невірний логін або пароль')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    # Перевірка на наявність повідомлень у сесії для реєстрації
    if 'register_flash' in session:
        category, message = session['register_flash']
        flash(message, category)
        session.pop('register_flash')  # Видаляємо повідомлення з сесії після його виведення

    if request.method == "POST":
        phone_number = request.form['phone-number']
        company_name = request.form['company-name']
        password = request.form['password']

        # Перевірка на дублювання назви компанії
        existing_company = Company.query.filter_by(name=company_name).first()
        if existing_company:
            session['register_flash'] = ('error', 'Компанія з такою назвою вже існує')
            return redirect(url_for('register'))

        # Перевірка на дублювання номера телефону
        existing_account = Account.query.filter_by(login=phone_number).first()
        if existing_account:
            session['register_flash'] = ('error', 'Акаунт з таким номером телефону вже існує')
            return redirect(url_for('register'))

        # Створення нової компанії та акаунта
        company = Company(name=company_name)
        db.session.add(company)
        db.session.commit()

        account = Account(
            login=phone_number,
            password=password,
            is_admin=True,
            company_id=company.id
        )
        db.session.add(account)
        db.session.commit()

        return redirect(url_for('login'))  # Перенаправлення на сторінку логіну

    return render_template('register.html')



if __name__ == '__main__':
    app.run(debug=True)
