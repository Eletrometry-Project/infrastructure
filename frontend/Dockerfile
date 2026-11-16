FROM node:24-bookworm-slim@sha256:c86ecead9e55a5210ac1727de38a4ca840bf03dcaf34dc9749addbf383b1920c
WORKDIR /srv/portal
COPY server.mjs policy.mjs smoke.mjs ./
COPY dist/ ./dist/
ENV PORT=8443 PORTAL_DATA=/var/lib/portal
USER node
EXPOSE 8443
CMD ["node","server.mjs"]
