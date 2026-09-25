FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn pydantic pydantic-settings argon2-cffi "sqlalchemy[asyncio]" asyncpg "resend>=2.47,<3"
COPY src ./src
ENV PYTHONPATH=/app/src
USER nobody
CMD ["uvicorn","movon_hr.main:app","--host","0.0.0.0","--port","8000"]
