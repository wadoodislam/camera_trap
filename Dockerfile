FROM nvcr.io/nvidia/l4t-base:r32.4.3

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

#ENV OPENBLAS_CORETYPE ARMV8

WORKDIR /src/

RUN apt-get upgrade && apt-get update
RUN apt-get install -y python3-pip

RUN python3 -m pip install --upgrade pip

COPY requirements.txt requirements.txt

RUN pip3 install -r requirements.txt


