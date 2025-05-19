from extensions import db

class Material(db.Model):
    __tablename__ = 'materials'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    company_id = db.Column(db.Integer, nullable=False)

    def __init__(self, name, company_id):
        self.name = name
        self.company_id = company_id