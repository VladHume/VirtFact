import os
import json

from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify
from config import SQLALCHEMY_DATABASE_URI, SQLALCHEMY_TRACK_MODIFICATIONS, SECRET_KEY
from extensions import db, migrate
import uuid
from werkzeug.utils import secure_filename
from models import *
from functools import wraps
import shutil
from datetime import datetime
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS
app.config['SECRET_KEY'] = SECRET_KEY
socketio = SocketIO(app)
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

def task_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        employee_id = session.get('employee_id')

        if not employee_id:
            return redirect(url_for('login'))  # або інша логіка, якщо неавторизований

        # Перевіряємо чи є "Alarm"
        alarm_task = Task.query.filter_by(responsible_id=employee_id, status='Alarm').first()
        if alarm_task:
            alarm = Alarm.query.filter_by(task_id=alarm_task.id).first()
            return redirect(url_for('alarm', alarm=alarm.id, task_id=alarm_task.id))

        # Перевіряємо чи є "У роботі"
        working_task = Task.query.filter_by(responsible_id=employee_id, status='У роботі').first()
        if working_task:
            return redirect(url_for('instruction_page', task_id=working_task.id))

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
                return redirect(url_for('home'))
            else:
                employee = Employee.query.filter_by(phone_number=login).first()
                if employee:
                    session['employee_id'] = employee.id
                    session['name'] = f"{employee.surname} {employee.name} {employee.middle_name}"
                else:
                    session['name'] = None
                return redirect(url_for('home_for_employee'))

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
    company_id = session['company_id']
    tasks = aTask.query.filter_by(company_id=company_id).all()

    task_data = []
    alarm = False

    for task in tasks:
        product = Product.query.filter_by(id=task.product_id, company_id=company_id).first()

        # Отримати відповідний запис з таблиці Task
        actual_task = Task.query.filter_by(
            company_id=company_id,
            admin_task_id=task.id
        ).first()

        if actual_task and actual_task.status == 'Alarm':
            alarm = True

        if product:
            task_data.append({
                'task_id': task.id,
                'product_id': product.id,
                'product_name': product.name
            })

    return render_template('main_admin.html', name=session['name'], task_data=task_data, alarm=alarm)

@socketio.on('check_alarm')
def handle_check_alarm():
    company_id = session['company_id']
    tasks = aTask.query.filter_by(company_id=company_id).all()

    alarm = False
    for task in tasks:
        actual_task = Task.query.filter_by(company_id=company_id, admin_task_id=task.id).first()
        if actual_task and actual_task.status == 'Alarm':
            alarm = True
            break

    emit('alarm_status', {'alarm': alarm})

@app.route('/home_for_employee', methods=['GET', 'POST'])
@login_required
@task_required
def home_for_employee():
    employee_id = session['employee_id']
    tasks = Task.query.filter(
        Task.responsible_id == employee_id,
        Task.status != "Завершене"
    ).all()
    task_data = []
    for task in tasks:
        operation = Operation.query.filter_by(id=task.operation_id).first()
        if operation:
            task_data.append({
                'task_id': task.id,
                'operation_id': operation.id,
                'operation_name': operation.name
            })
    return render_template('main_for_user.html', name=session['name'], tasks=task_data)

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
    data = request.get_json()
    name = data.get('name')
    company_id = session.get('company_id')
    if not company_id:
        return jsonify({"error": "Company ID not found in session"}), 400

    material = Material(name=name, company_id=company_id)
    db.session.add(material)
    db.session.commit()

    return jsonify({"id": material.id, "name": material.name})

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

@app.route('/edit_products_list')
@login_required
def edit_products_list():
    company_id = session.get('company_id')
    is_admin = session.get('is_admin')
    if not company_id:
        return "Company ID not found in session", 400

    products = Product.query.filter_by(company_id=company_id).all()
    return render_template('edit_products_list.html', products=products)

@app.route('/add_product', methods=['GET', 'POST'])
@login_required
def add_product():
    company_id = session.get('company_id')

    if not company_id:
        flash("Відсутній company_id в сесії", 'error')
        return redirect(url_for('home'))

    # Обробка POST-запиту — додавання нового виробу
    if request.method == 'POST':
        product_name = request.form.get('productName')

        if not product_name:
            flash("Назва виробу обов’язкова", 'error')
            return redirect(url_for('add_product'))

        existing = Product.query.filter_by(name=product_name, company_id=company_id).first()
        if existing:
            flash("Такий виріб вже існує", 'error')
            return redirect(url_for('add_product'))

        # Додати виріб
        product = Product(name=product_name, company_id=company_id)
        db.session.add(product)
        db.session.commit()

        flash("Виріб додано успішно", 'success')

        # Редірект із передачею product_id
        return redirect(url_for('add_product', product_id=product.id))

    # Обробка GET-запиту
    product = None
    selected_component = None

    product_id = request.args.get('product_id', type=int)
    if product_id:
        product = Product.query.filter_by(id=product_id, company_id=company_id).first()

    return render_template('add_product.html', product=product, selected_component=selected_component)

@app.route('/add_block/<int:product_id>', methods=['POST'])
@login_required
def add_block(product_id):
    data = request.get_json()
    block_name = data.get('block_name')

    if block_name:
        block = Block(name=block_name, product_id=product_id)
        db.session.add(block)
        db.session.commit()
        return '', 204  # success
    return 'Missing name', 400

@app.route('/add_detail/<int:block_id>', methods=['POST'])
@login_required
def add_detail(block_id):
    data = request.get_json()
    detail_name = data.get('detail_name')

    if detail_name:
        detail = Detail(name=detail_name, block_id=block_id)
        db.session.add(detail)
        db.session.commit()
        return '', 204
    return 'Missing name', 400

@app.route('/delete_product/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    company_id = session.get('company_id')
    if not company_id:
        return jsonify({'error': 'Company ID is missing'}), 400

    product = Product.query.filter_by(id=product_id, company_id=company_id).first()
    if not product:
        return jsonify({'error': 'Product not found'}), 404

    # Якщо потрібно, також видаляємо блоки й деталі
    for block in product.blocks:
        for detail in block.details:
            db.session.delete(detail)
        db.session.delete(block)

    db.session.delete(product)
    db.session.commit()
    return jsonify({'success': True}), 200

@app.route('/get_operations/<component_type>/<int:component_id>')
def get_operations(component_type, component_id):
    operations = Operation.query.filter_by(
        component_id=component_id,
        product_type=component_type
    ).all()

    result = [{'id': op.id, 'name': op.name} for op in operations]

    component_name = "Невідомо"
    if component_type == "product":
        obj = Product.query.get(component_id)
    elif component_type == "block":
        obj = Block.query.get(component_id)
    elif component_type == "detail":
        obj = Detail.query.get(component_id)
    else:
        obj = None

    if obj:
        component_name = obj.name

    return jsonify({
        'component_id': component_id,
        'type_name': component_type.capitalize(),
        'component_name': component_name,
        'operations': result
    })

@app.route('/add_operation/<int:component_id>')
@login_required
def add_operation(component_id):
    component_type = request.args.get('type')
    company_id = session.get('company_id')
    if not company_id:
        return "Company ID not found in session", 400

    locations = Location.query.filter_by(company_id=company_id).all()
    materials = Material.query.filter_by(company_id=company_id).all()
    tools = Tool.query.filter_by(company_id=company_id).all()

    # Приклад логіки залежно від типу
    dependencies = []
    if component_type == 'block':
        # Отримати інші блоки цього виробу
        block = Block.query.get(component_id)
        dependencies = Block.query.filter(
            Block.product_id == block.product_id,
            Block.id != component_id
        ).all()
    elif component_type == 'detail':
        # Отримати інші деталі цього блоку
        detail = Detail.query.get(component_id)
        dependencies = Detail.query.filter(
            Detail.block_id == detail.block_id,
            Detail.id != component_id
        ).all()

    component_name = "Невідомо"
    if component_type == "product":
        obj = Product.query.get(component_id)
        product_id = Product.query.get(component_id).id
    elif component_type == "block":
        obj = Block.query.get(component_id)
        product_id = Block.query.get(component_id).product_id
    elif component_type == "detail":
        obj = Detail.query.get(component_id)
        block_id = obj.block_id
        product_id = Block.query.get(block_id).product_id
    else:
        obj = None

    if obj:
        component_name = obj.name

    return render_template(
        'add_operation.html',
        component_type=component_type,
        locations=locations,
        materials=materials,
        tools=tools,
        dependencies=dependencies,
        component_name=component_name,
        component_id=component_id,
        product_id=product_id
    )

@app.route('/save_operation', methods=['POST'])
@login_required
def save_operation():
    data = request.form
    files = request.files

    name = data.get("name")
    component_id = int(data.get("component_id"))
    product_type = data.get("product_type")
    location_id = int(data.get("location"))
    tool_ids = data.getlist("tools[]")
    material_ids = data.getlist("materials[]")
    dependency_ids = data.getlist("dependencies[]")  # формат: ["type:id", ...]

    # 1. Створення операції
    operation = Operation(name=name, component_id=component_id, product_type=product_type)
    db.session.add(operation)
    db.session.commit()  # потрібно, щоб отримати operation.id

    # 2. Локація
    db.session.add(LocationO(location_id=location_id, operation_id=operation.id))

    # 3. Інструменти
    for tool_id in tool_ids:
        db.session.add(ToolO(tool_id=int(tool_id), operation_id=operation.id))

    # 4. Матеріали
    for material_id in material_ids:
        db.session.add(MaterialO(material_id=int(material_id), operation_id=operation.id))

    # 5. Залежності
    for dep in dependency_ids:
        dep_type, dep_id = dep.split(":")
        db.session.add(dComponent(component_id=int(dep_id), product_type=dep_type, operation_id=operation.id))

    # 6. Завантаження інструкцій
    uid = str(uuid.uuid4())
    base_path = os.path.join(UPLOAD_FOLDER)
    photo_path = save_files(files.getlist("photos"), os.path.join(base_path, "photos", uid))
    video_path = save_files(files.getlist("videos"), os.path.join(base_path, "videos", uid))
    text_path = save_files(files.getlist("texts"), os.path.join(base_path, "text_instructions", uid))

    instruction = Instruction(operation_id=operation.id, photo_path=photo_path, video_path=video_path, text_path=text_path)
    db.session.add(instruction)

    db.session.commit()
    return jsonify({"status": "success"})

def save_files(file_list, target_folder):
    if not os.path.exists(target_folder):
        os.makedirs(target_folder)

    for file in file_list:
        filename = file.filename
        if filename:
            file.save(os.path.join(target_folder, filename))
    return target_folder

@app.route('/delete_operation/<int:operation_id>', methods=['POST'])
@login_required
def delete_operation(operation_id):
    operation = Operation.query.get_or_404(operation_id)

    # Отримуємо інструкції для видалення шляхів до директорій
    instruction = Instruction.query.filter_by(operation_id=operation_id).first()

    if instruction:
        # Видалення директорій, якщо вони існують
        for path in [instruction.photo_path, instruction.video_path, instruction.text_path]:
            if path and os.path.exists(path):
                shutil.rmtree(path)

        db.session.delete(instruction)

    # Видаляємо пов'язані записи
    db.session.query(LocationO).filter_by(operation_id=operation_id).delete()
    db.session.query(ToolO).filter_by(operation_id=operation_id).delete()
    db.session.query(MaterialO).filter_by(operation_id=operation_id).delete()
    db.session.query(dComponent).filter_by(operation_id=operation_id).delete()

    db.session.delete(operation)
    db.session.commit()

    return jsonify({"status": "success"})

@app.route('/update_operation/<int:operation_id>', methods=['POST'])
@login_required
def update_operation(operation_id):
    operation = Operation.query.get_or_404(operation_id)
    data = request.form
    files = request.files
    deleted_files = request.form.get("deleted_files")
    deleted_files = json.loads(deleted_files) if deleted_files else {"photo": [], "video": [], "text": []}

    operation.name = data.get("name")

    # Завантаження інструкції або створення нової
    instruction = Instruction.query.filter_by(operation_id=operation_id).first()
    if not instruction:
        uid = str(uuid.uuid4())
        instruction = Instruction(
            operation_id=operation_id,
            photo_path=os.path.join(UPLOAD_FOLDER, "photos", uid),
            video_path=os.path.join(UPLOAD_FOLDER, "videos", uid),
            text_path=os.path.join(UPLOAD_FOLDER, "text_instructions", uid)
        )
        os.makedirs(instruction.photo_path, exist_ok=True)
        os.makedirs(instruction.video_path, exist_ok=True)
        os.makedirs(instruction.text_path, exist_ok=True)
        db.session.add(instruction)

    # Видалити окремі файли
    for category, path in [("photo", instruction.photo_path), ("video", instruction.video_path), ("text", instruction.text_path)]:
        for filename in deleted_files.get(category, []):
            file_path = os.path.join(path, filename)
            if os.path.exists(file_path):
                os.remove(file_path)

    # Додати нові файли
    save_files(files.getlist("photos"), instruction.photo_path)
    save_files(files.getlist("videos"), instruction.video_path)
    save_files(files.getlist("texts"), instruction.text_path)

    # Оновлення локації
    db.session.query(LocationO).filter_by(operation_id=operation_id).delete()
    db.session.add(LocationO(location_id=int(data.get("location")), operation_id=operation_id))

    # Очистити зв'язки
    db.session.query(ToolO).filter_by(operation_id=operation_id).delete()
    db.session.query(MaterialO).filter_by(operation_id=operation_id).delete()
    db.session.query(dComponent).filter_by(operation_id=operation_id).delete()

    # Нові зв’язки
    for t_id in data.getlist("tools[]"):
        db.session.add(ToolO(tool_id=int(t_id), operation_id=operation_id))
    for m_id in data.getlist("materials[]"):
        db.session.add(MaterialO(material_id=int(m_id), operation_id=operation_id))
    for dep in data.getlist("dependencies[]"):
        dep_type, dep_id = dep.split(":")
        db.session.add(dComponent(component_id=int(dep_id), product_type=dep_type, operation_id=operation_id))

    db.session.commit()
    return jsonify({"status": "success"})

@app.route('/edit_operation/<int:operation_id>')
@login_required
def edit_operation(operation_id):
    operation = Operation.query.get_or_404(operation_id)
    component_type = operation.product_type
    component_id = operation.component_id  # не product_id!
    company_id = session.get('company_id')

    if not company_id:
        return "Company ID not found in session", 400

    # Залежності
    dependencies = []
    if component_type == 'block':
        block = Block.query.get(component_id)
        dependencies = Block.query.filter(Block.product_id == block.product_id, Block.id != component_id).all()
    elif component_type == 'detail':
        detail = Detail.query.get(component_id)
        dependencies = Detail.query.filter(Detail.block_id == detail.block_id, Detail.id != component_id).all()

    # Витягування залежностей, інструментів, матеріалів
    # Залежні компоненти
    dependencies = dComponent.query.filter_by(operation_id=operation.id).all()
    selected_dependencies = [f"{d.product_type}:{d.component_id}" for d in dependencies]

    # Інструменти
    tools = ToolO.query.filter_by(operation_id=operation.id).all()
    selected_tools = [t.tool_id for t in tools]  # або форматуй, якщо треба

    # Матеріали
    materials = MaterialO.query.filter_by(operation_id=operation.id).all()
    selected_materials = [m.material_id for m in materials]

    location_o = LocationO.query.filter_by(operation_id=operation_id).first()
    location_id = location_o.location_id if location_o else None

    instruction = Instruction.query.filter_by(operation_id=operation_id).first()
    photo_files, video_files, text_files = [], [], []

    def list_files_in_dir(folder_path):
        if folder_path and os.path.exists(folder_path):
            return os.listdir(folder_path)
        return []

    if instruction:
        photo_files = list_files_in_dir(instruction.photo_path)
        video_files = list_files_in_dir(instruction.video_path)
        text_files = list_files_in_dir(instruction.text_path)

    # Назва компоненту
    obj = None
    if component_type == "product":
        obj = Product.query.get(component_id)
        product_id = Product.query.get(component_id).id
    elif component_type == "block":
        obj = Block.query.get(component_id)
        product_id = Block.query.get(component_id).product_id
    elif component_type == "detail":
        obj = Detail.query.get(component_id)
        block_id = obj.block_id
        product_id = Block.query.get(block_id).product_id
    component_name = obj.name if obj else "Невідомо"

    locations = Location.query.filter_by(company_id=company_id).all()
    materials = Material.query.filter_by(company_id=company_id).all()
    tools = Tool.query.filter_by(company_id=company_id).all()

    # Приклад логіки залежно від типу
    dependencies = []
    if component_type == 'block':
        # Отримати інші блоки цього виробу
        block = Block.query.get(component_id)
        dependencies = Block.query.filter(
            Block.product_id == block.product_id,
            Block.id != component_id
        ).all()
    elif component_type == 'detail':
        # Отримати інші деталі цього блоку
        detail = Detail.query.get(component_id)
        dependencies = Detail.query.filter(
            Detail.block_id == detail.block_id,
            Detail.id != component_id
        ).all()

    return render_template(
        'add_operation.html',
        component_id=component_id,
        component_type=component_type,
        component_name=component_name,
        locations=locations,
        materials=materials,
        tools=tools,
        dependencies=dependencies,
        selected_materials=selected_materials,
        selected_tools=selected_tools,
        selected_dependencies=selected_dependencies,
        location_id=location_id,
        operation=operation,
        edit_mode=True,
        product_id=product_id,
        photo_files=photo_files,
        video_files=video_files,
        text_files=text_files
    )

@app.route('/task_product_list')
@login_required
def task_product_list():
    company_id = session.get('company_id')
    is_admin = session.get('is_admin')
    if not company_id:
        return "Company ID not found in session", 400

    products = Product.query.filter_by(company_id=company_id).all()
    return render_template('add_task.html', products=products)

@app.route('/create_admin_task', methods=['POST'])
@login_required
def create_admin_task():
    data = request.get_json()
    product_id = data.get('product_id')
    company_id = session.get('company_id')
    if not company_id:
        return jsonify({'error': 'Company ID not found'}), 400
    if not product_id:
        return jsonify({'error': 'Product ID is required'}), 400

    admin_task = aTask(product_id=product_id, company_id=company_id)
    db.session.add(admin_task)
    db.session.commit()

    return jsonify({'admin_task_id': admin_task.id})

@app.route('/add_task', methods=['POST', 'GET'])
@login_required
def add_task():
    company_id = session.get('company_id')
    if not company_id:
        return "Company ID not found in session", 400

    employees = Employee.query.filter_by(company_id=company_id).all()
    employee_data = [
        {"id": e.id, "name": f"{e.surname} {e.name} {e.middle_name}"}
        for e in employees
    ]

    admin_task_id = request.args.get('admin_task_id', type=int)
    product_id = request.args.get('product_id', type=int)

    if admin_task_id:
        admin_task = aTask.query.filter_by(id=admin_task_id, company_id=company_id).first()
    elif product_id:
        admin_task = aTask(product_id=product_id, company_id=company_id)
        db.session.add(admin_task)
        db.session.commit()
    else:
        return "Product ID or Admin Task ID is required", 400

    product = Product.query.filter_by(id=admin_task.product_id, company_id=company_id).first()

    # Знайдемо вже створені завдання
    existing_tasks = Task.query.filter_by(admin_task_id=admin_task.id).all()
    task_map = [
        {
            "component_type": t.component_type,
            "product_id": t.product_id,
            "operation_id": t.operation_id,
            "id": t.id,
            "responsible_id": t.responsible_id,
            "status": t.status,
        }
        for t in existing_tasks
    ]

    return render_template(
        'assign_task.html',
        product=product,
        employees=employee_data,
        admin_task=admin_task,
        task_map=task_map  # передаємо у шаблон
    )

@app.route('/create_task', methods=['POST'])
@login_required
def create_task():
    data = request.get_json()
    operation_id = data.get('operation_id')
    employee_id = data.get('employee_id')
    component_id = data.get('component_id')
    component_type = data.get('component_type')
    admin_task_id = data.get('admin_task')

    company_id = session.get('company_id')

    try:
        task = Task.query.filter_by(
            admin_task_id=admin_task_id,
            product_id=component_id,
            operation_id=operation_id,
            component_type=component_type,
            company_id=company_id
        ).first()

        if task:
            task.responsible_id = employee_id
        else:
            task = Task(
                product_id=component_id,
                operation_id=operation_id,
                responsible_id=employee_id,
                status="Не активне",
                company_id=company_id,
                component_type=component_type,
                admin_task_id=admin_task_id
            )
            db.session.add(task)

        db.session.commit()

        return jsonify({'message': 'Завдання успішно призначено'})  # ← ДОДАНО
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/delete_admin_task/<int:task_id>', methods=['POST'])
@login_required
def delete_admin_task(task_id):
    # Знайди запис aTask
    admin_task = aTask.query.get(task_id)
    if not admin_task:
        return redirect(url_for('home'))

    # Видалити пов'язані записи з tasks
    Task.query.filter_by(admin_task_id=task_id).delete()

    # Видалити сам запис з admin_tasks
    db.session.delete(admin_task)
    db.session.commit()

    return redirect(url_for('home'))

@app.route('/task_status', methods=['POST', 'GET'])
@login_required
def task_status():
    company_id = session.get('company_id')
    if not company_id:
        return "Company ID not found in session", 400

    employees = Employee.query.filter_by(company_id=company_id).all()
    employee_data = [
        {"id": e.id, "name": f"{e.surname} {e.name} {e.middle_name}"}
        for e in employees
    ]

    admin_task_id = request.args.get('admin_task_id', type=int)
    product_id = request.args.get('product_id', type=int)

    if admin_task_id:
        admin_task = aTask.query.filter_by(id=admin_task_id, company_id=company_id).first()
    elif product_id:
        admin_task = aTask(product_id=product_id, company_id=company_id)
        db.session.add(admin_task)
        db.session.commit()
    else:
        return "Product ID or Admin Task ID is required", 400

    product = Product.query.filter_by(id=admin_task.product_id, company_id=company_id).first()

    existing_tasks = Task.query.filter_by(admin_task_id=admin_task.id).all()
    task_map = [
        {
            "component_type": t.component_type,
            "product_id": t.product_id,
            "operation_id": t.operation_id,
            "id": t.id,
            "responsible_id": t.responsible_id,
            "status": t.status,
        }
        for t in existing_tasks
    ]

    return render_template(
        'task_status.html',
        product=product,
        employees=employee_data,
        admin_task=admin_task,
        task_map=task_map
    )

@app.route('/instruction_page', methods=['POST', 'GET'])
@login_required
def instruction_page():
    task_id = request.args.get('task_id')
    task = Task.query.filter_by(id=int(task_id)).first()
    status = task.status
    operation = Operation.query.filter_by(id=task.operation_id).first()
    name = operation.name
    instruction = Instruction.query.filter_by(operation_id=operation.id).first()

    photos, videos, texts = [], [], []

    def normalize_path_for_url(path):
        if path:
            return path.replace('\\', '/')
        return path

    photo_path = ""
    video_path = ""
    text_path = ""

    if instruction:
        # Нормалізуємо шляхи для URL
        photo_path = normalize_path_for_url(instruction.photo_path) or ""
        video_path = normalize_path_for_url(instruction.video_path) or ""
        text_path = normalize_path_for_url(instruction.text_path) or ""

        # Для читання файлів із файлової системи коректно сформуємо абсолютні шляхи
        # Якщо в базі зберігаються відносні шляхи відносно static, додаємо їх
        base_static_path = os.path.join(os.getcwd(), 'static')  # або де у тебе корінь static

        def get_fs_path(url_path):
            # Перекладаємо URL-подібний шлях у шлях файлової системи (для os.listdir)
            # Наприклад, 'static/uploads/text_instructions/...' => '<поточна_директорія>/static/uploads/text_instructions/...'
            # Якщо url_path починається з "static/", відрізаємо static і додаємо base_static_path
            if url_path.startswith('static/'):
                relative_part = url_path[len('static/'):]
                return os.path.join(base_static_path, relative_part)
            else:
                # Якщо немає static на початку, вважай як є
                return os.path.join(base_static_path, url_path)

        if photo_path:
            photo_dir = get_fs_path(photo_path)
            if os.path.exists(photo_dir):
                photos = [f for f in os.listdir(photo_dir) if os.path.isfile(os.path.join(photo_dir, f))]

        if video_path:
            video_dir = get_fs_path(video_path)
            if os.path.exists(video_dir):
                videos = [f for f in os.listdir(video_dir) if os.path.isfile(os.path.join(video_dir, f))]

        if text_path:
            text_dir = get_fs_path(text_path)
            if os.path.exists(text_dir):
                texts = [f for f in os.listdir(text_dir) if os.path.isfile(os.path.join(text_dir, f))]

    material_links = MaterialO.query.filter_by(operation_id=operation.id).all()
    tool_links = ToolO.query.filter_by(operation_id=operation.id).all()
    location_link = LocationO.query.filter_by(operation_id=operation.id).first()

    material_ids = [m.material_id for m in material_links]
    materials = Material.query.filter(Material.id.in_(material_ids)).all() if material_ids else []

    tool_ids = [t.tool_id for t in tool_links]
    tools = Tool.query.filter(Tool.id.in_(tool_ids)).all() if tool_ids else []

    location = Location.query.filter_by(id=location_link.location_id).first() if location_link else None

    dependent_components = dComponent.query.filter_by(operation_id=operation.id).all()

    dependencies = []

    for dc in dependent_components:
        component_id = dc.component_id
        component_type = dc.product_type
        component_name = "Невідомо"
        product_id = None

        if component_type == "product":
            product = Product.query.get(component_id)
            if product:
                component_name = product.name
                product_id = product.id

        elif component_type == "block":
            block = Block.query.get(component_id)
            if block:
                component_name = block.name
                product_id = block.product_id

        elif component_type == "detail":
            detail = Detail.query.get(component_id)
            if detail:
                component_name = detail.name
                block = Block.query.get(detail.block_id)
                if block:
                    product_id = block.product_id

        dependencies.append({
            'type': component_type,
            'name': component_name,
            'product_id': product_id
        })

    return render_template(
        'open_task.html',
        name=name,
        materials=materials,
        location=location,
        tools=tools,
        dependencies=dependencies,
        image_files=photos,
        video_files=videos,
        text_files=texts,
        photo_path=photo_path,
        video_path=video_path,
        text_path=text_path,
        emp_name = session['name'],
        status=status,
        task_id=task_id
    )

@app.route('/start_task/<int:task_id>')
@login_required
def start_task(task_id):
    task = Task.query.filter_by(id=task_id).first()
    task.status = "У роботі"
    task.start_time = datetime.utcnow()
    db.session.add(task)
    db.session.commit()
    return redirect(url_for('instruction_page', task_id=task.id))

@app.route('/finish_task/<int:task_id>')
@login_required
def finish_task(task_id):
    task = Task.query.filter_by(id=task_id).first()
    task.status = "Завершене"
    task.end_time = datetime.utcnow()
    db.session.add(task)
    db.session.commit()
    return redirect(url_for('home_for_employee'))


@app.route('/alarm')
@login_required
def alarm():
    alarm_id = request.args.get('alarm')
    task_id = request.args.get('task_id')

    if alarm_id:
        alarm_obj = Alarm.query.filter_by(id=alarm_id).first()
        if alarm_obj:
            return render_template('alarm.html', name=session['name'], alarm=alarm_obj.text, task_id=task_id)
        else:
            return redirect(url_for('home_for_employee'))

    return render_template('alarm.html', name=session['name'], task_id=task_id)


@app.route('/submit_alarm/<int:task_id>', methods=['POST', 'GET'])
@login_required
def submit_alarm(task_id):
    text = request.form.get('operationName')
    alarm = Alarm(task_id=task_id, text=text)
    db.session.add(alarm)
    task = Task.query.filter_by(id=task_id).first()
    task.status = "Alarm"
    db.session.add(task)
    db.session.commit()
    return redirect(url_for('alarm', alarm = alarm.id, task_id=task_id))


def folder_create(name, relative_dir):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base_dir, relative_dir)

    os.makedirs(full_path, exist_ok=True)
    target_folder = os.path.join(full_path, name)

    if os.path.exists(target_folder):
        print(f'Folder "{name}" exists!')
    else:
        os.mkdir(target_folder)
        print(f'Folder "{name}" successfully created!')

@app.route('/alarm_for_admin')
@login_required
def alarm_for_admin():
    task_id = request.args.get('task_id')
    task = Task.query.filter_by(id=task_id).first()
    operation_id = task.operation_id
    operation = Operation.query.filter_by(id=operation_id).first()
    name = session.get('name')
    responsible_id = task.responsible_id
    employee = Employee.query.filter_by(id=responsible_id).first()
    responsible_name = f"{employee.surname} {employee.name} {employee.middle_name}"
    location_o = LocationO.query.filter_by(operation_id=operation.id).first()
    location = Location.query.filter_by(id=location_o.location_id).first()
    location_name = location.name
    alarm = Alarm.query.filter_by(task_id=task_id).first()
    return render_template('alarm_for_admin.html', operation=operation.name, task_id=task_id, name=name, responsible=responsible_name, location=location_name, alarm=alarm.text)

@app.route('/alarm_list_admin')
@login_required
def alarm_list_admin():
    company_id = session['company_id']
    tasks = Task.query.filter(
        Task.company_id == company_id,
        Task.status == "Alarm"
    ).all()
    task_data = []
    for task in tasks:
        operation = Operation.query.filter_by(id=task.operation_id).first()
        if operation:
            task_data.append({
                'task_id': task.id,
                'operation_id': operation.id,
                'operation_name': operation.name
            })
    return render_template('alarm_list_admin.html', name=session['name'], tasks=task_data)

@app.route('/delete_alarm/<int:task_id>')
@login_required
def delete_alarm(task_id):
    task = Task.query.filter_by(id=task_id).first()
    task.status = "У роботі"
    db.session.add(task)
    alarm = Alarm.query.filter_by(task_id=task_id).first()
    db.session.delete(alarm)
    db.session.commit()
    return redirect(url_for('home')) 

if __name__ == '__main__':
    folder_create('uploads', 'static')
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)

