ARG DOCKER_REGISTRY=
ARG NPM_REGISTRY=
FROM ${DOCKER_REGISTRY:-}node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN if [ -n "$NPM_REGISTRY" ]; then npm config set registry "$NPM_REGISTRY"; fi && npm ci
COPY . .
RUN npm run build

ARG DOCKER_REGISTRY=
FROM ${DOCKER_REGISTRY:-}nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
