FROM node:20-alpine

ENV NODE_ENV=development
ENV HOST=0.0.0.0
ENV PORT=3000

WORKDIR /app

# FIX: Pre-create the cache/module directories and enforce ownership before dropping root privileges
RUN mkdir -p .next node_modules && chown -R node:node /app

# Drop root privileges immediately for all subsequent commands
USER node

# Utilize Docker layer caching efficiently by installing dependencies before copying source code
COPY --chown=node:node package.json package-lock.json* ./
RUN npm ci

# Copy the remaining frontend application code
COPY --chown=node:node . .

EXPOSE 3000

CMD ["npm", "run", "dev"]