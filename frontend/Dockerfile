FROM node:24.19.0-slim@sha256:3638d9a6fe4030bd716be989438248074489337ba3275657f93595428be4fc03
ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund && chown -R node:node /app
RUN mkdir -p /app/.next && chown node:node /app/.next
COPY --chown=node:node . .
USER node
EXPOSE 3000
CMD ["npm", "run", "dev"]
