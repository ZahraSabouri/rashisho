FROM python:3.12

ARG UID=0
ARG GID=0

#RUN sed -i 's/deb\.debian\.org/ftp.nl.debian.org/g' /etc/apt/sources.list.d/debian.sources
#RUN echo 'Acquire::http::Proxy "http://172.16.0.6:8000/";' > /etc/apt/apt.conf.d/squid-deb-proxy.conf
# make apt fully noninteractive
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
 && apt-get install -y --no-install-recommends locales-all \
 && rm -rf /var/lib/apt/lists/*

# Just set the variables; don’t run update-locale
ENV LANG=fa_IR.UTF-8 \
    LANGUAGE=fa_IR:fa:en \
    LC_CTYPE=fa_IR.UTF-8 \
    LC_MESSAGES=fa_IR.UTF-8

#RUN locale-gen
RUN echo $UID $GID

RUN groupadd -g $GID -o django
RUN useradd -m -u $UID -g $GID -o -s /bin/bash django

ENV PATH /home/django/.local/bin:$PATH

WORKDIR /home/django
RUN chown -R $UID:$GID /home/django

# USER django:django

COPY --chown=django pyproject.toml poetry.lock ./

RUN python -m pip install --no-cache-dir -U pip setuptools wheel

RUN pip install --upgrade pip poetry==1.8.3 flake8 poetry-plugin-export
RUN poetry install --no-root
RUN poetry export -o requirements.txt && pip  install --no-cache-dir -r requirements.txt

COPY --chown=django . .

ENV PATH="/home/django/.local/bin:${PATH}"

EXPOSE 8000

RUN chown -R django:django .
RUN chmod +x entry.sh

ENTRYPOINT ["./entry.sh"]
