FROM node:22-slim

WORKDIR /app

COPY package*.json ./
RUN npm ci --production=false

COPY . .
RUN npm run build

ENV MCP_TRANSPORT=http
ENV PORT=8080
ENV SLM_API_URL=https://api.sealevel.tech

EXPOSE 8080

CMD ["node", "dist/index.js"]
