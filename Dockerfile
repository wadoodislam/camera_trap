FROM nvcr.io/nvidia/l4t-base:r32.4.3

WORKDIR /src/

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
RUN apt-get upgrade && apt-get update
COPY . .
#COPY requirements.txt requirements.txt


