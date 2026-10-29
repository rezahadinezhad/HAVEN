FROM mcr.microsoft.com/playwright@sha256:47b510dd9230bf0b9bfc9b20102241e577ea7a99334ab4c3ca19f19770e9b8ea
COPY haven-test-root.crt /usr/local/share/ca-certificates/haven-test-root.crt
RUN update-ca-certificates
USER pwuser
WORKDIR /work
