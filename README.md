# Face Recognition System (FastAPI + InsightFace)

A production-ready **Face Recognition Backend** built with **FastAPI**, **InsightFace**, and **PostgreSQL (pgvector)**.

This system allows you to:

* 📸 Register a user by uploading a face image
* 🔍 Identify a user by matching a face against stored embeddings
* 🚫 Prevent duplicate registrations (same face uploaded multiple times)
* ⚡ Perform fast similarity search using vector embeddings

---

## 🚀 Features

* Face detection & recognition using **InsightFace (ArcFace)**
* Pre-trained models (no ML training required)
* Face embedding storage using **pgvector**
* Cosine similarity–based matching
* Duplicate face prevention during registration
* Async FastAPI endpoints
* Clean, modular project structure

---

## 🧱 Tech Stack

| Layer            | Technology              |
| ---------------- | ----------------------- |
| API              | FastAPI                 |
| Face Model       | InsightFace (buffalo_l) |
| Image Processing | OpenCV                  |
| Database         | PostgreSQL              |
| Vector Search    | pgvector                |
| Language         | Python 3.11             |

---

## 📁 Project Structure

```
face-recognition-system/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI routes
│   ├── face_service.py  # Face logic & DB queries
│   └── database.py      # PostgreSQL connection
├── venv/
├── requirements.txt
└── README.md
```

---

## 🛠️ Installation & Setup

### 1️⃣ Create Virtual Environment (Python 3.11)

```bash
python3.11 -m venv venv
source venv/bin/activate
```

### 2️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

### 3️⃣ PostgreSQL Setup

Enable pgvector:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Create tables:

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    name TEXT,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE face_embeddings (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    embedding vector(512),
    created_at TIMESTAMP DEFAULT now()
);
```

---

## 🔐 Environment Variables

Create a `.env` file in the project root to store sensitive configuration.

### 📄 `.env` and `.env.example`

You should **separate real secrets from examples**.

---

## ▶️ Run the Server

```bash
uvicorn app.main:app --reload
```

Open Swagger UI:

```
http://127.0.0.1:8000/docs
```

---

## 🔌 API Endpoints

### 🔹 Register Face

**POST** `/register`

**Body (form-data):**

* `name` (text)
* `file` (image file)

**Behavior:**

* Extracts face embedding
* Checks if face already exists
* Registers new user if unique

**Success Response:**

```json
{
  "success": true,
  "user_id": "uuid",
  "message": "User registered successfully"
}
```

**Duplicate Face Response:**

```json
{
  "success": false,
  "message": "Face already registered",
  "existing_username": "John Doe",
  "similarity": 0.97
}
```

---

### 🔹 Identify Face

**POST** `/identify`

**Body (form-data):**

* `file` (image file)

**Success Match Response:**

```json
{
  "success": true,
  "matched": true,
  "user_id": "uuid",
  "username": "John Doe",
  "confidence": 0.88
}
```

**No Match Response:**

```json
{
  "success": true,
  "matched": false,
  "message": "User not found"
}
```

---

## 🧠 How Face Matching Works

1. Face detected from image
2. Converted into a **512-d embedding**
3. Compared with DB embeddings using **cosine distance**
4. Lowest distance = best match

### Thresholds

| Distance | Meaning               |
| -------- | --------------------- |
| < 0.30   | Same face (duplicate) |
| < 0.40   | Match                 |
| > 0.50   | Different person      |

---

## ⚙️ Why Async is Used

* Handles multiple requests efficiently
* Prevents blocking during file upload & DB calls
* Improves scalability

⚠️ Note: ML inference itself is CPU-bound; async improves I/O, not model speed.

---

## 🧪 Testing

Use **Postman** or **Swagger UI**:

* Body type must be `form-data`
* Key must be exactly `file`
* Upload a real image (jpg/png)

---

## 🔐 Security & Best Practices

* Store **embeddings**, not raw images
* Use HTTPS in production
* Get user consent for biometric data
* Secure database credentials

---

## 🚀 Future Improvements

* Multiple images per user
* HNSW index for faster search
* Recognition history logs
* Liveness / anti-spoofing detection
* Docker & cloud deployment
* Frontend UI (React)

---

## 👨‍💻 Author

Built as a backend face recognition system using modern Python and ML tooling.

---

## 📜 License

For learning and internal use. Add a license if deploying publicly.
