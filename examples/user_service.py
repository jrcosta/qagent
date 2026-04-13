def create_user(data):
    if not data.get("email"):
        return {"error": "missing email"}

    if not data.get("name"):
        return {"error": "missing name error"}

    save_user(data)
    return {"status": "ok"}