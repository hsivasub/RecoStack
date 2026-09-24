# Prometheus Dockerfile — RecoStack
#
# Minimal Prometheus image with the recoStack scrape config baked in.
# Config can be overridden at runtime via volume mount.

FROM prom/prometheus:latest

COPY config/prometheus/prometheus.yml /etc/prometheus/prometheus.yml

EXPOSE 9090

# Default command uses the baked-in config
CMD ["--config.file=/etc/prometheus/prometheus.yml", "--storage.tsdb.path=/prometheus", "--web.console.libraries=/usr/share/prometheus/console_libraries", "--web.console.templates=/usr/share/prometheus/consoles"]