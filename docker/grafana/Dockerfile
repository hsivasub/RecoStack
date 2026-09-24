# Grafana Dockerfile — RecoStack
#
# Pre-provisions the Prometheus datasource and RecoStack dashboard.
# Dashboard JSON and provisioning files are baked into the image.

FROM grafana/grafana:latest

# Copy provisioning configs (datasource + dashboard provider)
COPY config/grafana/provisioning /etc/grafana/provisioning/

# Copy dashboard JSON files
COPY config/grafana/dashboards /etc/grafana/provisioning/dashboards/

ENV GF_SECURITY_ADMIN_USER=admin
ENV GF_SECURITY_ADMIN_PASSWORD=admin
ENV GF_INSTALL_PLUGINS=

EXPOSE 3000