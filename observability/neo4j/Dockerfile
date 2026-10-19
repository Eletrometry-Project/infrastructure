FROM neo4j:5.26.30-community
LABEL org.opencontainers.image.title="Eletrometry Neo4j Lab"
LABEL org.opencontainers.image.description="Neo4j Community com verificacao autenticada; senhas e dados externos a imagem"
COPY health.sh /opt/eletrometry-health.sh
USER root
RUN chmod 0755 /opt/eletrometry-health.sh
USER neo4j
HEALTHCHECK --interval=30s --timeout=15s --start-period=120s --retries=5 CMD ["/opt/eletrometry-health.sh"]
