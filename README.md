# 🛠️ Production Server Setup Instructions

Follow these steps to prepare a fresh Ubuntu server for running the **AP Minimal Dockerized app**.

---

## 🔧 Update & Install Dependencies
```bash
sudo apt update && sudo apt install -y \
    tar zip unzip vim curl wget git gnupg2 lsb-release ca-certificates \
    software-properties-common net-tools htop
```

## 🐍 Install Python & Pip (Optional – only for manual scripts)
```bash
sudo apt install -y python3 python3-pip
```

## 🐳 Install Docker & Docker Compose
```bash
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

docker --version
docker compose version
```

## 👥 Add Current User to Docker Group
```bash
sudo groupadd docker
sudo usermod -aG docker $USER
newgrp docker
```

## 🚀 Enable and Start Docker Service
```bash
sudo systemctl enable docker
sudo systemctl start docker
sudo systemctl status docker
```

## 🔐 Clone the Repository
```bash
git clone git@github.com:Dusanbg11/ap-minimal-docker.git
cd ap-minimal-docker
```

⚠️ Make sure you're on the correct branch (usually `main`):
```bash
git checkout main
```

## ⚙️ Configure Environment Variables
Rename `.env.example` to `.env` and edit the values:
```bash
cp .env.example .env
nano .env
```

Replace the default values, especially:
```
SECRET_KEY=<your_secure_generated_key>
APP_ADMIN_USERNAME=<your_username>
APP_ADMIN_PASSWORD=<your_password>
MYSQL_ROOT_PASSWORD=<your_root_password>
MYSQL_PASSWORD=<your_user_password>
```

Generate a secure secret key:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
# or
openssl rand -hex 32
```

## 🧽 Disable init.sql After First Setup (Optional but Recommended)
If you're running for the second time or on production, comment out the `init.sql` line in your `docker-compose.yml` file:
```yaml
# - ./init.sql:/docker-entrypoint-initdb.d/init.sql
```

## 📦 Start the Containers
```bash
docker compose up -d
```

## 📋 Verify Everything Is Running
```bash
docker ps
```

You should see containers for the Flask app and the MariaDB database running.
