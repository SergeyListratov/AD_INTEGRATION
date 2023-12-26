# pull official base image
FROM python:3.11.3-slim-buster

RUN apt-get update && \
apt-get --yes install build-essential python3-dev libmemcached-dev libldap2-dev libsasl2-dev libzbar-dev  ldap-utils tox lcov valgrind && \
apt-get clean


RUN mkdir /ad_api

WORKDIR /ad_api

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

RUN chmod a+x /ad_api/docker/app.sh

# RUN alembic upgrade head

CMD ["gunicorn", "app.main:app", "--workers", "1", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind=0.0.0.0:8000"]
