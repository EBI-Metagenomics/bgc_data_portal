FROM python:3.10-slim

WORKDIR /app

COPY ../ . 

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000
ENV PYTHONUNBUFFERED=0

CMD ["python", "mananage.py", "runserver", "0.0.0.0:8000"]