FROM python:3

ARG branch=master
RUN pip install git+https://github.com/grnet/amaltheia@$branch --no-cache
WORKDIR /amaltheia

ENTRYPOINT ["amaltheia"]
