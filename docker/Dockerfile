FROM python:3.5
RUN ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime
ADD sources.list /etc/apt/sources.list
RUN apt-get update && apt-get install -y \
        vim \
        cron \
        rsyslog \
        && rm -rf /var/lib/apt/lists/*

COPY bashrc /root/.bashrc
COPY crontab /opt/crontab
COPY run.sh /bin/run.sh

VOLUME ["/var/log/crontab/", "/etc/rsyslog.d/"]

ENTRYPOINT ["sh", "/bin/run.sh"]

RUN echo 'export PATH=/opt/conda/bin:$PATH' > /etc/profile.d/conda.sh && \
    wget --quiet https://repo.continuum.io/archive/Anaconda3-5.1.0-Linux-x86_64.sh -O ~/anaconda.sh && \
    /bin/bash ~/anaconda.sh -b -p /opt/conda && \
    rm ~/anaconda.sh

ENV PATH /opt/conda/bin:$PATH


RUN conda install numpy matplotlib pandas jupyter notebook

RUN pip install jinja2
RUN pip install pyyaml==3.12
RUN pip install cubi
RUN pip install pygsheets
RUN pip install requests
RUN pip install Django
RUN pip install websocket-client==0.40.0
RUN pip install jupyter notebook
RUN apt-get update && apt-get install -y python3-dev  \
        && rm -rf /var/lib/apt/lists/*
run wget https://tenet.dl.sourceforge.net/project/ta-lib/ta-lib/0.4.0/ta-lib-0.4.0-src.tar.gz
run tar zxvf ta-lib-0.4.0-src.tar.gz
run cd ta-lib && ./configure && make && make install
run pip install TA-Lib
env LD_LIBRARY_PATH /usr/local/lib
run pip install dateparser
RUN pip install autobahn==17.9.3 && \
    pip install certifi==2017.11.5 && \
    pip install chardet==3.0.4 && \
    pip install cryptography==2.1.4 && \
    pip install dateparser==0.6.0 && \
    pip install pyOpenSSL==17.5.0 && \
    pip install requests==2.18.4 && \
    pip install service-identity==17.0.0 && \
    pip install Twisted==17.9.0
