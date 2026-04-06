FROM node:20-bookworm-slim

WORKDIR /app/apps/web

COPY apps/web/package*.json ./
RUN npm ci --include=optional

COPY apps /app/apps

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
