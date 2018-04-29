#!/bin/sh

_uid=`id -u`

if [ $_uid = 0 ]; then
    rsyslogd

    mkdir -p /var/log/crontab
    env | awk -F'=' '{print $1"=\"" $2 "\"" }' > /var/log/crontab/crontab.env

    crontab /opt/crontab

    cron -f &
fi

exec "$@"
