FROM node:20-alpine AS build

WORKDIR /app

COPY package.json .
RUN npm install

COPY . .

# Pass in the URL during build
ARG EXPO_PUBLIC_API_URL
ENV EXPO_PUBLIC_API_URL=$EXPO_PUBLIC_API_URL

# We force Expo to bind to LAN (0.0.0.0 equivalent) and disable the interactive terminal UI
ENV CI=true
CMD ["npx", "expo", "start", "--web", "--port", "8081", "--host", "lan"]