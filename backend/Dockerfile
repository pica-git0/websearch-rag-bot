FROM node:18-alpine

WORKDIR /app

# 패키지 파일 복사
COPY package*.json ./

# 의존성 설치
RUN npm install

# 애플리케이션 코드 복사
COPY . .

# TypeScript 빌드
RUN npm run build

# 포트 노출
EXPOSE 4000

# 애플리케이션 실행
CMD ["node", "dist/main.js"]
