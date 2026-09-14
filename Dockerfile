# Бот написан на голой стандартной библиотеке: ни pip install, ни build-стадии.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    BRB_RUNTIME_DIR=/runtime

RUN useradd --create-home --uid 10001 brb \
    && mkdir -p /runtime \
    && chown brb:brb /runtime

WORKDIR /app
COPY src/ /app/src/

# Состояние (SQLite, конфиги, team.txt) приходит томом и в образе не хранится.
VOLUME ["/runtime"]
USER brb

CMD ["python", "-X", "utf8", "/app/src/discussion.py"]
