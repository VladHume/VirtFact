from extensions import db

class ToolO(db.Model):
    __tablename__ = 'tools_for_operation'

    id = db.Column(db.Integer, primary_key=True)
    tool_id = db.Column(db.Integer, nullable=False)
    operation_id = db.Column(db.Integer, nullable=False)

    def __init__(self, tool_id, operation_id):
        self.tool_id = tool_id
        self.operation_id = operation_id