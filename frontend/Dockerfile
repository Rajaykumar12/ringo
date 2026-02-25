FROM node:20-alpine AS build

WORKDIR /app

COPY package.json .
RUN npm install

COPY . .

# Pass in the URL during build
ARG EXPO_PUBLIC_API_URL
ENV EXPO_PUBLIC_API_URL=$EXPO_PUBLIC_API_URL

RUN npx expo export --platform web

# Serve with node and serve package
FROM node:20-alpine
WORKDIR /app
RUN npm install -g serve
COPY --from=build /app/dist ./dist

EXPOSE 3000
CMD ["serve", "-s", "dist", "-l", "3000"]