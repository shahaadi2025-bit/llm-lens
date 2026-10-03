FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Real-model inference deps are opt-in: build with --build-arg WITH_ML=1
ARG WITH_ML=0
COPY requirements-ml.txt .
RUN if [ "$WITH_ML" = "1" ]; then pip install --no-cache-dir -r requirements-ml.txt; fi
COPY . .
RUN useradd --create-home lens && chown -R lens /srv
USER lens
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
