FROM python:3.13.13-slim@sha256:aa938a849bcb82dce8f49480f056ab82bf5c1c3ebc294f0430f37b6820e7f286
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY deploy/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r requirements.txt
COPY src/cc_cep /app/cc_cep
USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "cc_cep.app:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
