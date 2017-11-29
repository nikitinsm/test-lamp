FROM python:3.6

COPY requirements.freezed.pip /tmp/requirements.freezed.pip

RUN pip install -r /tmp/requirements.freezed.pip

COPY ./ /tmp/lamp/

WORKDIR /tmp/lamp

RUN python setup.py install