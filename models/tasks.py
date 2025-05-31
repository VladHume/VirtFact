from extensions import db

class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    product_id = db.Column(db.Integer, nullable=False)
    operation_id = db.Column(db.Integer, nullable=False)
    responsible_id = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50))
    company_id = db.Column(db.Integer, nullable=False)
    component_type = db.Column(db.String(50))
    admin_task_id = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)

    def __init__(self, product_id, operation_id, responsible_id, status, company_id, component_type, admin_task_id, start_time=None, end_time=None):
        self.product_id = product_id
        self.operation_id = operation_id
        self.responsible_id = responsible_id
        self.status = status
        self.company_id = company_id
        self.component_type = component_type
        self.admin_task_id = admin_task_id
        self.start_time = start_time
        self.end_time = end_time