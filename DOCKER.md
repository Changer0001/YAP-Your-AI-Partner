# YAP — Docker Installation & Setup

**Quick start for Docker Compose (recommended).**

---

## **Requirements**

- **Docker** (~100 MB)
- **Docker Compose** (included in Docker Desktop)
- **Disk space:** ~5 GB (Ollama models)
- **RAM:** 4 GB minimum, 8 GB recommended
- **CPU or GPU:** Works on both

---

## **1. Install Docker**

### **Linux (Ubuntu/Debian)**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker
```

### **Mac/Windows**
- Download **Docker Desktop**: https://www.docker.com/products/docker-desktop
- Install, restart

### **Verify**
```bash
docker --version
docker compose version
```

---

## **2. Start YAP**

### **Option A: CPU Only (Default)**
```bash
# Clone or download YAP
git clone https://github.com/Changer0001/YAP-Your-AI-Partner.git
cd YAP-Your-AI-Partner

# Start services
docker compose up -d

# Watch logs
docker compose logs -f yap

# When ready (takes 1–2 min to pull models):
# Open: http://localhost:8000/
```

### **Option B: GPU (NVIDIA)**
```bash
# Uncomment GPU section in docker-compose.yml

# Install nvidia-docker:
# https://github.com/NVIDIA/nvidia-docker

# Start with GPU:
docker compose up -d

# Verify GPU detected:
docker compose exec ollama ollama list
```

---

## **3. First Run (Setup)**

1. **Open browser:** `http://localhost:8000/`
2. **Click "Setup"**
3. **Enter setup key** (check logs or `docker compose logs yap` for `setup_key:`)
4. **Create first admin account** (username/password)
5. **Done!**

---

## **4. Common Commands**

### **Start/Stop**
```bash
docker compose up -d      # Start in background
docker compose stop       # Stop services
docker compose down       # Stop + remove containers (keep data)
docker compose down -v    # Stop + remove everything (reset)
```

### **Logs**
```bash
docker compose logs yap         # YAP logs
docker compose logs ollama      # Ollama logs
docker compose logs -f yap      # Follow (tail) logs
```

### **Restart**
```bash
docker compose restart yap
docker compose restart ollama
```

### **Shell Access**
```bash
docker compose exec yap bash           # Access YAP container
docker compose exec ollama bash        # Access Ollama container
```

### **Check Status**
```bash
docker compose ps
docker compose ps --no-trunc

# Health check:
curl http://localhost:8000/api/auth/status
```

---

## **5. Customization**

### **Change Models**
Edit `docker-compose.yml`:
```yaml
environment:
  CHAT_MODEL: "qwen2.5:7b"  # Change model
  EMBED_MODEL: "nomic-embed-text"
```

Then restart:
```bash
docker compose restart yap
```

### **Change Port**
Edit `docker-compose.yml`:
```yaml
yap:
  ports:
    - "3000:8000"  # Access at http://localhost:3000/
```

### **Persistent Configuration**
Create `.env` file in YAP directory:
```bash
# .env
OLLAMA_HOST=http://ollama:11434
LLM_TEMPERATURE=0.15
ALLOW_REGISTRATION=false
YAP_FOUNDER="Your Name"
```

Restart: `docker compose restart yap`

---

## **6. Access from Network**

### **Local Network (LAN)**
```bash
# Find server IP
hostname -I  # Linux/Mac
ipconfig     # Windows

# Access from another machine:
http://YOUR-SERVER-IP:8000/
```

### **Internet (Tailscale Funnel)**
```bash
# Inside YAP container:
docker compose exec yap tailscale funnel --bg --https=3000 8000

# Share URL:
https://your-machine.ts.net/
```

---

## **7. Backup & Restore**

### **Backup Data**
```bash
# Copy persistent volumes
docker compose exec yap tar czf - -C /app data | gzip > yap-backup.tar.gz
```

### **Restore Data**
```bash
# Stop services
docker compose down

# Restore
docker run --rm -v yap_data:/app/data -v $(pwd):/backup alpine \
  tar xzf /backup/yap-backup.tar.gz -C /app

# Start
docker compose up -d
```

---

## **8. Troubleshooting**

### **Models not downloading**
```bash
# Check Ollama logs
docker compose logs ollama

# Manually pull model:
docker compose exec ollama ollama pull qwen2.5:3b
```

### **Port already in use**
```bash
# Change port in docker-compose.yml
# Or kill existing process:
lsof -i :8000
kill -9 <PID>
```

### **High memory usage**
- Ollama models are large (3B = ~2.5 GB RAM)
- GPU helps (offloads to VRAM)
- Normal behavior

### **Slow responses**
- First query may be slow (model loading)
- Subsequent queries faster
- CPU-only: expect 1–2s per query
- GPU: expect 0.3–0.5s per query

### **Container keeps restarting**
```bash
# Check logs
docker compose logs yap

# Common causes:
# - OLLAMA_HOST unreachable (Ollama not running)
# - Port conflict
# - Out of disk space
```

---

## **9. Update YAP**

```bash
# Pull latest code
git pull origin main

# Rebuild image
docker compose build --no-cache

# Restart
docker compose up -d
```

---

## **10. Uninstall**

```bash
# Remove containers + volumes
docker compose down -v

# Remove images (optional)
docker rmi yap-your-ai-partner-yap ollama/ollama
```

---

## **Support**

- **Logs:** `docker compose logs -f`
- **Issues:** Check GitHub issues
- **Docs:** See `docs/` directory

---

**Questions?** Check logs first: `docker compose logs yap`
