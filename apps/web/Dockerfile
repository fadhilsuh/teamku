FROM node:22-alpine AS build
WORKDIR /app
ARG MOVON_API_ORIGIN
ENV MOVON_API_ORIGIN=${MOVON_API_ORIGIN}
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM node:22-alpine
WORKDIR /app
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
ENV HOSTNAME=0.0.0.0
USER node
EXPOSE 3000
CMD ["node","server.js"]
