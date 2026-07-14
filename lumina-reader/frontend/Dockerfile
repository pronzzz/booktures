FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./

# Install dependencies
RUN npm install

COPY . .

# Expose port 3000 for Vite
EXPOSE 3000

# Default command for dev
CMD ["npm", "run", "dev", "--", "--host"]
