# syntax=docker/dockerfile:1
FROM public.ecr.aws/docker/library/python:3.12.10-alpine3.20
WORKDIR /code
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
# RUN apk add --no-cache gcc musl-dev linux-headers
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
EXPOSE 8080
COPY . .
CMD ["flask", "run", "--host=0.0.0.0", "--port=8080"]
