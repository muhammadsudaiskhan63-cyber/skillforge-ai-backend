class User:
    def __init__(self, full_name, email, password, role="student"):
        self.full_name = full_name
        self.email = email
        self.password = password
        self.role = role