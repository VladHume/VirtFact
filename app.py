import os

from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify
from config import SQLALCHEMY_DATABASE_URI, SQLALCHEMY_TRACK_MODIFICATIONS, SECRET_KEY
from extensions import db, migrate
import uuid
from werkzeug.utils import secure_filename
from models import *
from functools import wraps

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS
app.config['SECRET_KEY'] = SECRET_KEY

db.init_app(app)
migrate.init_app(app, db)

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
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

        if account and account.check_password(password):
            session['user_id'] = account.id
            session['company_id'] = account.company_id
            if account.is_admin:
                session['name'] = "Адміністратор"
            else:
                employee = Employee.query.filter_by(phone_number=login).first()
                if employee:
                    session['employee_id'] = employee.id
                    session['name'] = f"{employee.surname} {employee.name} {employee.middle_name}"
                else:
                    session['name'] = None
            return redirect(url_for('home'))
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

@app.route('/home', methods=['GET', 'POST'])
@login_required
def home():
    return render_template('main_admin.html', name=session['name'])

@app.route('/employees', methods=['GET', 'POST'])
@login_required
def employees():
    company_id = session.get('company_id')
    is_admin = session.get('is_admin')
    if not company_id:
        return "Company ID not found in session", 400

    employees = Employee.query.filter_by(company_id=company_id).all()
    return render_template('edit_employees_list.html', employees=employees, name=session['name'])

@app.route('/add_employee', methods=['GET', 'POST'])
@login_required
def add_employee():
    return render_template('add_employee.html')

@app.route('/add_employee_action', methods=['POST'])
@login_required
def add_employee_action():
    if 'add_emp_flash' in session:
        category, message = session['add_emp_flash']
        flash(message, category)
        session.pop('add_emp_flash')

    if request.method == 'POST':
        surname = request.form['surname']
        name = request.form['name']
        patronymic = request.form['patronymic']
        phone = request.form['phone']
        photo = request.files['photo']
        password = request.form['password']

        # Якщо акаунт з таким логіном (тобто номером телефону) вже існує
        existing_account = Account.query.filter_by(login=phone).first()
        if existing_account:
            session['add_emp_flash'] = ('error', 'Акаунт з таким номером телефону вже існує')
            return redirect(url_for('add_employee'))

        photo_path = None
        if photo and allowed_file(photo.filename):
            ext = os.path.splitext(photo.filename)[1]
            unique_name = f"{uuid.uuid4().hex}{ext}"
            photo.save(os.path.join(UPLOAD_FOLDER, unique_name))
            photo_path = os.path.join(UPLOAD_FOLDER, unique_name)

        employee = Employee(
            name=name,
            surname=surname,
            middle_name=patronymic,
            phone_number=phone,
            photo_path=photo_path,
            company_id=session['company_id']
        )

        account = Account(
            login=phone,
            is_admin=False,
            company_id=session['company_id'],
            password=password
        )

        db.session.add(employee)
        db.session.add(account)
        db.session.commit()
        return redirect(url_for('employees'))

    return redirect(url_for('add_employee'))

@app.route('/delete_employee/<int:employee_id>', methods=['POST'])
@login_required
def delete_employee(employee_id):
    employee = db.session.get(Employee, employee_id)
    if not employee:
        return jsonify({'error': 'Працівника не знайдено'}), 404

    # Видалення акаунта
    account = Account.query.filter_by(login=employee.phone_number).first()
    if account:
        db.session.delete(account)

    # Видалення фото, якщо воно існує
    if employee.photo_path and os.path.exists(employee.photo_path):
        try:
            os.remove(employee.photo_path)
        except Exception as e:
            return jsonify({'error': f'Помилка при видаленні фото: {str(e)}'}), 500

    db.session.delete(employee)
    db.session.commit()
    return jsonify({'success': True}), 200

@app.route('/edit_employee/<int:employee_id>', methods=['GET', 'POST'])
@login_required
def edit_employee(employee_id):
    employee = db.session.get(Employee, employee_id)
    if not employee:
        flash('Працівника не знайдено', 'error')
        return redirect(url_for('employees'))

    # Отримати відповідний акаунт
    account = Account.query.filter_by(login=employee.phone_number).first()

    if request.method == 'POST':
        surname = request.form['surname']
        name = request.form['name']
        patronymic = request.form['patronymic']
        new_phone = request.form['phone']
        photo = request.files.get('photo')

        # Перевірка: якщо номер змінено — чи не зайнятий він іншим акаунтом
        if new_phone != employee.phone_number:
            existing_account = Account.query.filter_by(login=new_phone).first()
            if existing_account:
                flash('Акаунт з таким номером телефону вже існує', 'error')
                return redirect(url_for('edit_employee', employee_id=employee.id))
            if account:
                account.login = new_phone  # оновлюємо логін акаунта

        if photo and allowed_file(photo.filename):
            if employee.photo_path:
                full_old_path = os.path.join(app.root_path, 'static', employee.photo_path)
                if os.path.exists(full_old_path):
                    os.remove(full_old_path)

            ext = os.path.splitext(photo.filename)[1]
            unique_name = f"{uuid.uuid4().hex}{ext}"
            full_path = os.path.join(app.root_path, UPLOAD_FOLDER, unique_name)  # повний шлях для збереження
            photo.save(full_path)
            photo_path = os.path.join('uploads', unique_name)
            employee.photo_path = photo_path

        # Оновлення працівника
        employee.name = name
        employee.surname = surname
        employee.middle_name = patronymic
        employee.phone_number = new_phone

        db.session.commit()
        return redirect(url_for('employees'))

    return render_template('edit_employee_info.html', employee=employee)

@app.route('/edit_materials_list')
@login_required
def edit_materials_list():
    company_id = session.get('company_id')
    if not company_id:
        return "Company ID not found in session", 400

    materials = Material.query.filter_by(company_id=company_id).all()
    return render_template('edit_materials_list.html', materials=materials)

@app.route('/add-material', methods=['POST'])
@login_required
def add_material():
    if request.method == 'POST':
        data = request.get_json()
        name = data.get('name')
        company_id = session.get('company_id')
        if not company_id:
            return "Company ID not found in session", 400
        material = Material(name=name, company_id=company_id)
        db.session.add(material)
        db.session.commit()
    return redirect(url_for('edit_materials_list'))

@app.route('/edit-material/<int:material_id>', methods=['PUT'])
@login_required
def edit_material(material_id):
    data = request.get_json()
    new_name = data.get('name')
    material = Material.query.get(material_id)
    if not material:
        return jsonify({'error': 'Матеріал не знайдено'}), 404
    material.name = new_name
    db.session.commit()
    return '', 204


@app.route('/delete-material/<int:material_id>', methods=['DELETE'])
@login_required
def delete_material(material_id):
    material = Material.query.get(material_id)
    if not material:
        return jsonify({'error': 'Матеріал не знайдено'}), 404
    db.session.delete(material)
    db.session.commit()
    return '', 204


@app.route('/edit_locations_list')
@login_required
def edit_locations_list():
    company_id = session.get('company_id')
    if not company_id:
        return "Company ID not found in session", 400

    locations = Location.query.filter_by(company_id=company_id).all()
    return render_template('edit_locations_list.html', locations=locations)

@app.route('/add-location', methods=['POST'])
@login_required
def add_location():
    if request.method == 'POST':
        data = request.get_json()
        name = data.get('name')
        company_id = session.get('company_id')
        if not company_id:
            return "Company ID not found in session", 400
        location = Location(name=name, company_id=company_id)
        db.session.add(location)
        db.session.commit()
    return redirect(url_for('edit_locations_list'))

@app.route('/edit-location/<int:location_id>', methods=['PUT'])
@login_required
def edit_location(location_id):
    data = request.get_json()
    new_name = data.get('name')
    location = Location.query.get(location_id)
    if not location:
        return jsonify({'error': 'Локацію не знайдено'}), 404
    location.name = new_name
    db.session.commit()
    return '', 204


@app.route('/delete-location/<int:location_id>', methods=['DELETE'])
@login_required
def delete_location(location_id):
    location = Location.query.get(location_id)
    if not location:
        return jsonify({'error': 'Локацію не знайдено'}), 404
    db.session.delete(location)
    db.session.commit()
    return '', 204

@app.route('/edit_tools_list')
@login_required
def edit_tools_list():
    company_id = session.get('company_id')
    if not company_id:
        return "Company ID not found in session", 400

    tools = Tool.query.filter_by(company_id=company_id).all()
    return render_template('edit_tools_list.html', tools=tools)

@app.route('/add-tool', methods=['POST'])
@login_required
def add_tool():
    data = request.get_json()
    name = data.get('name')
    company_id = session.get('company_id')
    if not company_id:
        return jsonify({'error': 'Company ID not found in session'}), 400

    tool = Tool(name=name, company_id=company_id)
    db.session.add(tool)
    db.session.commit()
    return jsonify({'id': tool.id}), 201

@app.route('/edit-tool/<int:tool_id>', methods=['PUT'])
@login_required
def edit_tool(tool_id):
    data = request.get_json()
    new_name = data.get('name')
    tool = Tool.query.get(tool_id)
    if not tool:
        return jsonify({'error': 'Інструмент не знайдено'}), 404
    tool.name = new_name
    db.session.commit()
    return '', 204

@app.route('/delete-tool/<int:tool_id>', methods=['DELETE'])
@login_required
def delete_tool(tool_id):
    tool = Tool.query.get(tool_id)
    if not tool:
        return jsonify({'error': 'Інсрумент не знайдено'}), 404
    db.session.delete(tool)
    db.session.commit()
    return '', 204


if __name__ == '__main__':
    app.run(debug=True)
