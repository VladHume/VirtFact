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

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == "POST":
        phone_number = request.form['phone-number']
        company_name = request.form['company-name']
        password = request.form['password']

        # Перевірка на дублювання назви компанії
        existing_company = Company.query.filter_by(name=company_name).first()
        if existing_company:
            flash('Компанія з такою назвою вже існує', 'error')
            return render_template('register.html')

        # Перевірка на дублювання номера телефону
        existing_account = Account.query.filter_by(login=phone_number).first()
        if existing_account:
            flash('Акаунт з таким номером телефону вже існує', 'error')
            return render_template('register.html')

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

        return redirect(url_for('login'))

    return render_template('register.html')


if __name__ == '__main__':
    app.run(debug=True)
