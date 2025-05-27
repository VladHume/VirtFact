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


if __name__ == '__main__':
    app.run(debug=True)
