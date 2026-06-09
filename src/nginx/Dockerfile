FROM nginx:1.27-alpine

RUN apk add --no-cache openssl curl

# Generate self-signed cert for development (replace with real certs in production)
RUN mkdir -p /etc/nginx/ssl && \
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/key.pem \
    -out /etc/nginx/ssl/cert.pem \
    -subj "/C=US/ST=State/L=City/O=WorkTicket/CN=localhost" && \
    chown -R nginx:nginx /etc/nginx/ssl && \
    apk del openssl

COPY nginx.conf /etc/nginx/nginx.conf

RUN mkdir -p /var/cache/nginx /var/run && \
    chown -R nginx:nginx /var/cache/nginx /var/run /etc/nginx

EXPOSE 80 443

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -sf http://localhost/healthz || exit 1

USER nginx

CMD ["nginx", "-g", "daemon off;"]
