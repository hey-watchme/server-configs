# WatchMe Nginx Configurations

This repository stores the Nginx configuration files for the WatchMe platform.

## 🎯 Goal

- Manage Nginx configuration files under Git version control.
- Prevent accidental configuration changes and enable easy rollbacks.

## 🔧 How to Use

### 1. Modifying Configurations

**DO NOT directly edit files on the server.**

1.  **Clone this repository** to your local machine.
2.  **Create a new branch** for your changes (e.g., `feature/add-new-service`).
3.  **Modify the configuration files** as needed.
4.  **Commit and push** your changes to the branch.
5.  **Create a Pull Request** on GitHub for review.

### 2. Deploying Configurations to the Server

After the Pull Request is approved and merged into the `main` branch:

1.  **SSH into the EC2 server**.
2.  **Navigate to the configuration directory**:
    ```bash
    cd /path/to/your/nginx/configs
    ```
3.  **Pull the latest changes**:
    ```bash
    git pull origin main
    ```
4.  **Test the configuration** to ensure there are no syntax errors:
    ```bash
    sudo nginx -t
    ```
5.  **If the test is successful, reload Nginx** to apply the changes:
    ```bash
    sudo systemctl reload nginx
    ```

## 📂 File Structure

- `sites-available/`: Contains all possible configuration files.
- `sites-enabled/`: Contains symbolic links to the configurations in `sites-available` that you want to be active.
