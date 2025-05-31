from extensions import db

class aTask(db.Model):
    __tablename__ = 'admin_tasks'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    product_id = db.Column(db.Integer, nullable=False)
    company_id = db.Column(db.Integer, nullable=False)

    def __init__(self, product_id, company_id):
        self.product_id = product_id
        self.company_id = company_id