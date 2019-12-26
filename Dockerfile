FROM python:3

ARG ssh_id_rsa=ssh_id_rsa
ARG ssh_config=ssh_config
ARG jobs=jobs
ARG branch=master

RUN pip install git+https://github.com/grnet/amaltheia@$branch

WORKDIR /amaltheia

COPY $ssh_id_rsa /amaltheia/ssh_id_rsa
COPY $ssh_config /amaltheia/ssh_config
COPY $jobs /amaltheia

ENTRYPOINT ["amaltheia"]
