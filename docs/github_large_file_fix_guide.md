# 🛡️ GitHub Large File Error – Prevention & Recovery Guide

> **Date:** 2025-08-05

GitHub rejects any file over **100 MB**. This guide helps you:

- ✅ Recover from an accidental large file push
- 🔒 Prevent it from happening again

---

## 🚨 Problem

You pushed a file over 100MB and received an error like:

```
error: File xyz is 240.5 MB; this exceeds GitHub's file size limit of 100.00 MB
```

---

## 🛠️ How to Fix It (Step-by-Step)

### 1. Install `git-filter-repo` (if not already)

```bash
pip install git-filter-repo
```

---

### 2. Remove Large Files from Git History

Navigate to the repo root:

```bash
cd your-repo-folder
```

Run:

```bash
git filter-repo --path venv311 --invert-paths
```

> Replace `venv311` with the actual file or folder name to remove.

---

### 3. Re-add GitHub Remote (if removed)

```bash
git remote add origin https://github.com/YourUsername/YourRepo.git
```

---

### 4. Force Push Clean Repo

```bash
git push origin --force --all
git push origin --force --tags
```

---

### 5. Re-clone Clean Repo (Recommended)

```bash
cd ..
git clone https://github.com/YourUsername/YourRepo.git clean_repo
cd clean_repo
```

---

## 🔒 Prevention Checklist

| ✅ Task                             | Purpose                          |
|------------------------------------|----------------------------------|
| Add large files to `.gitignore`    | Prevents accidental commits      |
| Ignore virtual environments        | Avoids adding `venv`, `.env`     |
| Never commit `.dll`, `.lib`, `.pt` | Too large for GitHub             |
| Use `git status` & `git diff`      | Review changes before pushing    |
| Use Git LFS for large binaries     | https://git-lfs.com              |

---

## 📂 Recommended `.gitignore` for Python Projects

```gitignore
# Python cache
__pycache__/
*.py[cod]

# Virtual environment
venv*/
.venv/
.env/

# Logs and databases
*.log
*.db

# Compiled extensions
*.so
*.dll
*.lib
*.exe

# Model files
*.pt
*.pkl

# IDE files
.vscode/
.idea/

# OS metadata
.DS_Store
Thumbs.db
```

---

## ✅ You're Safe Now

By following this guide:

- Git history is clean ✅  
- `.gitignore` protects you ✅  
- Pushes won’t fail due to file size ✅
