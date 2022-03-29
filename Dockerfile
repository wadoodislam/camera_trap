FROM nvcr.io/nvidia/l4t-base:r32.4.3

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /src/

RUN apt-get upgrade && apt-get update
RUN apt-get install -y python3-pip

COPY . .

RUN pip3 install -r requirements.txt


