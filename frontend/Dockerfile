FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Pass your backend's URL here when building for deployment
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# Serve with nginx for production
FROM nginx:alpine

ARG VITE_API_URL
COPY --from=build /app/dist /usr/share/nginx/html

# The CSP in nginx.conf needs the API origin baked in. It's already known at build
# time (same value the bundle is compiled against), so substitute it here rather
# than dragging in the runtime template/envsubst machinery. Empty VITE_API_URL
# means same-origin, which 'self' already covers.
COPY nginx.conf /etc/nginx/conf.d/default.conf
RUN sed -i "s|\${API_ORIGIN}|${VITE_API_URL}|g" /etc/nginx/conf.d/default.conf

# Run unprivileged. The stock image starts its master as root; give the nginx user
# ownership of everything it writes and move the pid file out of root-owned /var/run.
RUN sed -i 's|^pid .*|pid /tmp/nginx.pid;|' /etc/nginx/nginx.conf \
    && sed -i '/user  nginx;/d' /etc/nginx/nginx.conf \
    && chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /etc/nginx/conf.d

USER nginx

# Unprivileged processes can't bind <1024, so serve on 8080.
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
