FROM node:20-alpine

WORKDIR /app

COPY package*.json ./

RUN npm install

COPY . .

EXPOSE 5173

# Expose host to allow external connections in docker
CMD ["npm", "run", "dev", "--", "--host"]
