# Stage 1 — build the React app
FROM node:20-slim AS builder

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build
# This produces a /app/dist folder with static HTML/JS/CSS

# Stage 2 — serve it with nginx
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80