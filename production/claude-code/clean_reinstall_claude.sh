#!/bin/bash
# This script performs a deep clean and reinstallation of claude-code.

echo "Starting the complete cleaning and reinstallation process for claude-code..."

# Step 1: Forcibly remove old files, symbolic links, and directories
echo "
Step 1: Forcibly removing old files and directories..."
rm -f ~/.npm-global/bin/claude
rm -rf ~/.npm-global/lib/node_modules/@anthropic-ai
echo "Old files removed."

# Step 2: Force clean the npm cache
echo "
Step 2: Clearing the npm cache..."
npm cache clean --force
echo "npm cache cleared."

# Step 3: Reinstall claude-code
echo "
Step 3: Reinstalling @anthropic-ai/claude-code..."
npm install -g @anthropic-ai/claude-code@2.0.5

# Step 4: Verify the installation
echo "
Step 4: Verifying the installation..."
# Source the .zshrc file to ensure the PATH is updated for the current session
source ~/.zshrc > /dev/null 2>&1

CLAUDE_PATH=$(which claude)
if [ -n "$CLAUDE_PATH" ]; then
  echo "✅ 'claude' command found at: $CLAUDE_PATH"
  CLAUDE_VERSION=$(claude --version)
  echo "✅ Version: $CLAUDE_VERSION"
  echo "
-----------------------------------------------------------------"
  echo "✅ Process complete. claude-code has been cleanly reinstalled."
  echo "
If the command breaks again, just run this script:"
  echo "bash ~/Desktop/clean_reinstall_claude.sh"
  echo "-----------------------------------------------------------------"
else
  echo "
❌ ERROR: 'claude' command could not be found after installation."
  echo "There might be an issue with your ~/.zshrc PATH configuration."
fi
