import secrets

def generate_code(length=8):
    return secrets.token_hex(length // 2)[:length]

