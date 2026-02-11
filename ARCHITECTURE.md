# SHMS Backend: Production Architecture Guide

This document explains the production-ready folder structure implemented for the SHMS Backend, following Clean Architecture principles and senior developer best practices.

## 📁 Directory Structure

```text
SHMS-Backend/
├── alembic/                # Database migration scripts
├── app/                    # Main application package
│   ├── api/                # API Layer (FastAPI specific)
│   │   ├── v1/             # API Versioning
│   │   │   ├── endpoints/  # Route handlers (Controllers)
│   │   │   │   ├── admin.py
│   │   │   │   ├── auth.py
│   │   │   │   └── face.py
│   │   │   └── router.py   # Aggregates v1 endpoints
│   │   └── deps.py         # Shared dependencies (Auth, DB session)
│   ├── core/               # Centralized config & security
│   │   ├── config.py       # Pydantic-Settings & ENV management
│   │   └── security.py     # JWT, Hashing, Auth utilities
│   ├── db/                 # Database infrastructure
│   │   └── session.py      # Connection pooling & session logic
│   ├── models/             # SQLAlchemy/DB models (future-proofed)
│   ├── schemas/            # Pydantic models (Data Transfer Objects)
│   ├── services/           # Business Logic Layer (Internal Services)
│   │   ├── face_service.py # Image processing & face matching
│   │   └── user_service.py # User & Role management logic
│   ├── utils/              # Cross-cutting utilities (Networking, etc.)
│   └── main.py             # App entry point & initialization
├── tests/                  # Mirroring app structure for testing
├── .env                    # Environment variables
├── alembic.ini            # Alembic configuration
└── requirements.txt        # Project dependencies
```

## 🏗 Why this structure is better?

### 1. Separation of Concerns
Each layer has a distinct responsibility. Routes in `api/` only handle HTTP concerns, while `services/` contains pure business logic. This makes it easier to replace parts of the system (e.g., swapping the database or switching from FastAPI to another framework).

### 2. High Scalability
- **Versioning**: Using `api/v1/` allows for non-breaking API updates by introducing `v2/` in parallel.
- **Domain Boundries**: Endpoints and services are split by domain (auth, user, face), allowing multiple teams to work on different areas without conflicts.

### 3. Production Readiness
- **Centralized Config**: All settings are typed and validated at startup using Pydantic, preventing runtime failures due to missing environment variables.
- **Shared Dependencies**: Authentication and DB session logic are reusable across all endpoints via FastAPI's `Depends`.

## 🏷 Naming Conventions

- **Endpoints**: Plural nouns for collections (e.g., `/officers`), singular for specific resources (`/officers/{id}`).
- **Services**: Suffix with `_service.py` to distinguish from other modules.
- **Schemas**: Clear naming like `UserCreate`, `UserUpdate`, `UserOut` to indicate intent.

## 🤝 Team Collaboration Best Practices

1. **Keep Routes Thin**: Business logic belongs in `services/`.
2. **Use Type Hints**: Python type hints improve IDE support and catch bugs early.
3. **Consistent Errors**: Use the shared exception handlers or standardized response schemas.
4. **Environment Isolation**: Always use the `Settings` class instead of raw `os.getenv`.
