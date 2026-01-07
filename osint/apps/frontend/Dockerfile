FROM node:20-alpine AS build

WORKDIR /app

COPY apps/frontend/package*.json ./
RUN npm install

COPY apps/frontend ./

ARG VITE_API_URL=http://localhost:8000
ARG VITE_WS_URL=ws://localhost:8000/ws/monitor
ARG VITE_NEO4J_URI=bolt://localhost:7687
ARG VITE_NEO4J_USER=neo4j
ARG VITE_NEO4J_PASSWORD=please-change-me
ARG VITE_PERSON_API_URL=

ENV VITE_API_URL=${VITE_API_URL} \
    VITE_WS_URL=${VITE_WS_URL} \
    VITE_NEO4J_URI=${VITE_NEO4J_URI} \
    VITE_NEO4J_USER=${VITE_NEO4J_USER} \
    VITE_NEO4J_PASSWORD=${VITE_NEO4J_PASSWORD} \
    VITE_PERSON_API_URL=${VITE_PERSON_API_URL}

RUN npm run build

FROM nginx:1.25-alpine AS production

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
