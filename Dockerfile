# Dockerfile (part of voipgrid/swiftdrop) builds a multi-daemon service
#   that has postfix handle incoming mail and sending received mail to
#   OpenStack Swift.
FROM debian:stretch

# ARG is used at build time only, unlike ENV which pollutes the final image
ARG DEBIAN_FRONTEND=noninteractive

# Default to haproxy UPSTREAM_PROXY_PROTOCOL; but you may disable if you want.
ENV UPSTREAM_PROXY_PROTOCOL=haproxy

# Fetch curl, postfix and python3-swiftclient
# (we only need curl during the build, but it doesn't hurt to keep)
RUN apt-get update -q && \
    apt-get dist-upgrade -y && \
    apt-get install -y --no-install-recommends \
    ca-certificates curl postfix python3 python3-swiftclient && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# GoSpawn + postfix-wait.py + postfix to foreground postfix
COPY postfix-wait.py /usr/local/bin/
RUN curl -so gospawn https://junk.devs.nu/go/gospawn.upx && \
    printf '%s%s  gospawn\n' \
      939760978b2e56dd2c60d7c85d27770612aa862007f9f6b81d756a23761ed09f \
      c074f1f1badf3b00fd68b66a8ab7f0498a5424db68a59d86264a90ef34815b48 | \
      sha512sum -c && \
    install -m0555 gospawn /usr/local/bin/gospawn && rm gospawn && \
    gospawn /dev/log -- sh -c "logger 'Logging works!'" >&2

# confd manages configuration templates with various sources (etcd, env) to
# render the templates (this is done in the entrypoint)
RUN path=releases/download/v0.16.0/confd-0.16.0-linux-amd64 && \
    curl -Lso confd https://github.com/kelseyhightower/confd/$path && \
    printf '%s%s  confd\n' \
      68c93fd6db55c7de94d49f596f2e3ce8b2a5de32940b455d40cb05ce832140eb \
      cc79a266c1820da7c172969c72a6d7367b465f21bb16b53fa966892ee2b682f1 | \
      sha512sum -c && \
    install -m0555 confd /usr/local/bin/confd && rm confd

# Config
COPY confd/ /etc/confd
COPY main.cf master.cf /etc/postfix/

# The swiftdrop daemon that pushes incoming mails to swift
COPY swiftdrop.py /usr/local/bin/

# Entrypoint, renamed so the ps list clearly shows what this image does
COPY entrypoint.sh /swiftdrop-entrypoint
ENTRYPOINT ["/swiftdrop-entrypoint"]

# We listen on 25 as a real MX (we run as root)
EXPOSE 25

# GoSpawn manages both postfix and the swiftdrop daemon
CMD ["/usr/local/bin/gospawn", "/dev/log", \
     "--", "service", "postfix", "start", \
     "--", "postfix-wait.py", \
     "--", "swiftdrop.py", "--run-as-proxy"]
