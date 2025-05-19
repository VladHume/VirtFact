from extensions import db

class Employee(db.Model):
    __tablename__ = 'employees'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    surname = db.Column(db.String(100), nullable=False)
    middle_name = db.Column(db.String(100))
    phone_number = db.Column(db.String(20))
    photo_path = db.Column(db.String(255))
    company_id = db.Column(db.Integer, nullable=False)

    def __init__(self, name, surname, middle_name, phone_number, photo_path, company_id):
        self.name = name
        self.surname = surname
        self.middle_name = middle_name
        self.phone_number = phone_number
        self.photo_path = photo_path
        self.company_id = company_id


    def __repr__(self):
        return f'<Employee {self.name} {self.surname}>'
