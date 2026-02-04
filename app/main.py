from fastapi import FastAPI, UploadFile, File, Form
from app.face_service import get_embedding, find_match, register_user

app = FastAPI()


@app.post("/identify")
async def identify_face(file: UploadFile = File(...)):
    image_bytes = await file.read()
    embedding = get_embedding(image_bytes)

    if embedding is None:
        return {"success": False, "message": "No face detected"}

    user_id, username, distance = find_match(embedding)

    if user_id and distance < 0.4:
        return {
            "success": True,
            "matched": True,
            "user_id": user_id,
            "username": username,
            "confidence": round(1 - distance, 2)
        }

    return {
        "success": True,
        "matched": False,
        "message": "User not found"
    }

@app.post("/register")
async def register_face(
    name: str = Form(...),
    file: UploadFile = File(...)
):
    image_bytes = await file.read()
    embedding = get_embedding(image_bytes)

    if embedding is None:
        return {
            "success": False,
            "message": "Invalid image or no face detected"
        }

    # 🔍 CHECK IF FACE ALREADY EXISTS
    existing_user_id, existing_username, distance = find_match(embedding)

    if distance is not None and distance < 0.30:
        return {
            "success": False,
            "message": "Face already registered",
            "existing_user_id": existing_user_id,
            "existing_username": existing_username,
            "similarity": round(1 - distance, 2)
        }

    # ✅ REGISTER NEW USER
    user_id = register_user(name, embedding)

    return {
        "success": True,
        "user_id": user_id,
        "message": "User registered successfully"
    }
