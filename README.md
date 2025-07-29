# AP Minimal (Dockerized)

This is a lightweight web application for managing users, servers, and applications — powered by Flask and MariaDB.

## 📦 Features
- Flask-based web interface
- MariaDB with Docker volume
- Admin panel with audit logs
- Ready for deployment on any Docker-capable server

## 🚀 Quick Start

```bash
git clone https://github.com/Dusanbg11/ap-minimal-docker.git
cd ap-minimal-docker
cp .env.example .env  # Or create your own .env file
docker-compose up --build -d
