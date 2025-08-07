# WatchMe Server Configurations

This repository stores all critical server configuration files for the WatchMe platform, including **Nginx** and **systemd**.

## 🎯 Goal

- Manage all server configurations under Git version control.
- Prevent accidental configuration changes and enable easy rollbacks.
- Provide a single source of truth for server settings.

## 📂 File Structure

```
.
├── systemd/              # systemd service files
│   ├── watchme-api-1.service
│   └── ...
├── sites-available/      # Nginx configuration files
│   └── api.hey-watch.me
└── README.md
```

---

## 🔧 How to Use

**DO NOT directly edit files on the server.** All changes must go through this Git repository.

### 1. Modifying Configurations

1.  **Clone this repository** to your local machine.
2.  **Create a new branch** for your changes (e.g., `feature/add-new-service`).
3.  **Modify the configuration files** in the appropriate directory (`systemd/` or `sites-available/`).
4.  **Commit and push** your changes to the branch.
5.  **Create a Pull Request** on GitHub for review.

### 2. Deploying Configurations to the Server

After the Pull Request is approved and merged into the `main` branch, SSH into the EC2 server and follow the appropriate deployment steps.

#### Deploying Nginx Changes

1.  **Navigate to the local clone** of this repository on the server.
2.  **Pull the latest changes**: `git pull origin main`
3.  **Copy the new configuration**: `sudo cp sites-available/api.hey-watch.me /etc/nginx/sites-available/`
4.  **Test the configuration**: `sudo nginx -t`
5.  **If successful, reload Nginx**: `sudo systemctl reload nginx`

#### Deploying systemd Changes

1.  **Navigate to the local clone** of this repository on the server.
2.  **Pull the latest changes**: `git pull origin main`
3.  **Copy the new service file**: `sudo cp systemd/your-service-name.service /etc/systemd/system/`
4.  **Reload the systemd daemon**: `sudo systemctl daemon-reload`
5.  **Enable and start the new service**:
    ```bash
    sudo systemctl enable your-service-name.service
    sudo systemctl start your-service-name.service
    ```
6.  **Check the status**: `sudo systemctl status your-service-name.service`