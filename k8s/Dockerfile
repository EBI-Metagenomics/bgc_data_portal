FROM python:3.10-slim

WORKDIR /app

COPY ../ . 

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000
ENV PYTHONUNBUFFERED=0


CMD ["gunicorn", "--bind", ":8000", "--workers", "3", "--timeout", "520", "bgc_data_portal.wsgi"]