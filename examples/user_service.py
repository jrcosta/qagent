def create_user(data):
    if not data.get("email"):
        return {"error": "missing email"}

    save_user(data)
    return {"status": "ok"}