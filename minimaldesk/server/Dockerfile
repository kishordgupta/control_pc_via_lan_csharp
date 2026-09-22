FROM php:8.4-cli-bookworm
RUN docker-php-ext-install pcntl \
    && groupadd --gid 10001 minimaldesk \
    && useradd --uid 10001 --gid minimaldesk --no-create-home minimaldesk \
    && mkdir /data && chown minimaldesk:minimaldesk /data
WORKDIR /app
COPY --chown=minimaldesk:minimaldesk . /app
USER 10001:10001
ENV MINIDESK_DATA=/data MINIDESK_LISTEN=0.0.0.0:8080 MINIDESK_MAX_CLIENTS=20
EXPOSE 8080
CMD ["php", "relay.php"]
