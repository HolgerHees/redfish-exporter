FROM python:3.13.2-alpine3.21
LABEL maintainer="Holger Hees <holger.hees@gmail.com>"
LABEL source_repository="https://github.com/sapcc/redfish-exporter"

ARG FOLDERNAME=redfish_exporter

RUN mkdir /${FOLDERNAME}
RUN mkdir /${FOLDERNAME}/collectors
RUN mkdir /${FOLDERNAME}/helper

WORKDIR /${FOLDERNAME}

RUN pip3 install --break-system-packages --upgrade pip --ignore-install
COPY requirements.txt /${FOLDERNAME}
RUN pip3 install --break-system-packages --no-cache-dir -r requirements.txt

COPY *.py /${FOLDERNAME}/
COPY collectors/ /${FOLDERNAME}/collectors/
COPY helper/ /${FOLDERNAME}/helper/
COPY config.yml.default /${FOLDERNAME}/config.yml
COPY secrets.yml.default /${FOLDERNAME}/secrets.yml

CMD ["python3", "main.py"]
