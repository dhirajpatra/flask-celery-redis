# base image
# FROM python:3.8.0-alpine
FROM python:3.6-alpine3.9

LABEL MAINTAINER="Dhiraj Patra <dpatra@presto.com>"

WORKDIR /api

RUN apk add libc-dev gcc curl-dev python3-dev libressl-dev

ENV C_FORCE_ROOT true

ENV HOST 0.0.0.0
ENV PORT 5000
ENV DEBUG true


# ENV GROUP_ID=1000 \
#     USER_ID=1000

# install requirements
ADD ./requirements.txt /api/requirements.txt
RUN pip install --upgrade pip
RUN pwd
RUN pip install -r requirements.txt

# expose the app port
EXPOSE 5000

RUN pip install gunicorn

COPY . /api


RUN addgroup -S celery -g 1000 && adduser -S celery -u 1000 -G celery

# run the app server in production with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "5", "app:app"]