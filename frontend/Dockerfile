FROM node:20-alpine AS build

WORKDIR /app

COPY package.json .
RUN npm install

COPY . .

# Pass in the URL during build
ARG EXPO_PUBLIC_API_URL
ENV EXPO_PUBLIC_API_URL=$EXPO_PUBLIC_API_URL

# Start the Expo web development server directly
# Note: For production, this is heavily resource intensive but matches local development exactly
EXPOSE 8081
# We bind to 0.0.0.0 so Azure can route traffic to it
CMD ["npx", "expo", "start", "--web", "--port", "8081", "--host", "0.0.0.0"]