FROM python:3.10-buster

RUN mkdir /var/lib/nile-demo/
COPY requirements.txt /var/lib/nile-demo/
RUN pip install -r /var/lib/nile-demo/requirements.txt

COPY app/ /var/lib/nile-demo/app/
RUN cd /var/lib/nile-demo/ && \
    ls -lA && \
    flask init-db

WORKDIR /var/lib/nile-demo/
CMD flask run --host=0.0.0.0
