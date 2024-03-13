# base image
# FROM python:3.8.0-alpine
FROM python:3.6-alpine3.9

LABEL MAINTAINER="Dhiraj Patra <dpatra@presto.com>"

WORKDIR /queue

RUN apk add libc-dev gcc curl-dev python3-dev libressl-dev

ENV C_FORCE_ROOT true

# ENV GROUP_ID=1000 \
#     USER_ID=1000
RUN pip install --upgrade pip
ADD ./requirements.txt /queue/requirements.txt
RUN pwd
RUN pip install -r requirements.txt

COPY . /queue


RUN addgroup -S celery -g 1000 && adduser -S celery -u 1000 -G celery

# production
ENTRYPOINT celery -A tasks worker --loglevel=info