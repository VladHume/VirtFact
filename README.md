# VirtFact

**VirtFact** is a Flask-based web application for managing production processes, tasks, employees, materials, tools, and products.  
The system allows administrators to create and assign tasks, while employees can receive instructions, mark task completion, and report problems (Alarms).

## Main Features
- **Authentication and Registration**
  - Register new companies and administrators
  - Login for administrators and employees
- **Employee Management**
  - Add, edit, and delete employees
- **Management of Materials, Tools, Locations, and Products**
  - Full CRUD operations for all entities
- **Creating Products and Their Components (blocks, details)**
- **Operations**
  - Add operations for products, blocks, and details
  - Upload photo, video, and text instructions
  - Assign materials, tools, locations, and dependencies
- **Tasks**
  - Administrator creates an "administrative" task for a product
  - Assign tasks to employees
  - Track statuses: `Inactive`, `In Progress`, `Completed`, `Alarm`
- **Alarm System**
  - Employee can report a problem
  - Administrator can view the list of active Alarms
- **Real-time Updates**
  - Uses `Flask-SocketIO` for real-time status updates

## Project Setup

### 1. Clone the repository
```bash
git clone https://github.com/VladHume/VirtFact.git
cd VirtFact
```

### 2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate  # Linux
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure settings
Create a `config.py` file with the following variables:
```python
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:password@localhost/yourdb'
SQLALCHEMY_TRACK_MODIFICATIONS = False
SECRET_KEY = 'your_secret_key'
```

### 5. Initialize the database
```bash
flask db init
flask db migrate
flask db upgrade
```

### 6. Run the application
```bash
python app.py
```

## User Roles
- **Administrator**
  - Manages employees, materials, tools, and products
  - Creates and assigns tasks
  - Views and closes Alarms
- **Employee**
  - Receives tasks with instructions
  - Can start and finish tasks
  - Can report problems (Alarm)
