# Steam Game Remover

An automated tool for removing free licenses from your Steam account.

## YES! YOU HAVE TO MANUALLY REFRESH COOKIES EVERY DAY! Script speed is ~130 games/per day. 

## Overview

Steam Game Remover is a containerized Python application that automatically removes free licenses from your Steam account. It uses Playwright to automate interactions with the Steam store, allowing for continuous operation and monitoring.

## Features

- Automatically removes free Steam licenses in bulk
- Runs as a Docker container for easy deployment
- Telegram notifications for status updates
- Continuous operation mode with configurable scan intervals
- Daily summary reports
- Error handling and retry mechanisms

## Prerequisites

- Docker and Docker Compose
- A valid Steam account with cookies exported to Netscape format
- (Optional) A Telegram bot token and chat ID for notifications

## Setup

1. **Clone the repository**

2. **Export your Steam cookies**
   - Log into your Steam account in a browser
   - Use a browser extension to export cookies in Netscape format
   - Save the exported cookies as `cookie.txt` in the project directory

3. **Convert cookies format**
   ```
   python convert_cookie.py
   ```
   ```
   python3 convert_cookie.py
   ```
   This will convert the Netscape-format cookies to the JSON format required by Playwright.

4. **Configure Telegram notifications (optional)**
   - Create a Telegram bot using [BotFather](https://t.me/botfather)
   - Get your chat ID
   - Edit the `steam-game-remover.py` file to add your bot token and chat ID:
     ```python
     self.telegram_token = "YOUR_BOT_TOKEN"
     self.chat_id = "YOUR_CHAT_ID"
     ```

5. **Build and run the container**
   ```
   docker-compose up -d
   ```

## Configuration

You can modify the following variables in `steam-game-remover.py`:

- `CONTINUOUS_OPERATION`: Set to `True` to keep scanning even when no packages are found
- `SCAN_INTERVAL`: Time in seconds between scans when no packages are found (default: 600)

## Understanding the Files

- `convert_cookie.py`: Script to convert Netscape format cookies to JSON format
- `steam-game-remover.py`: Main application that handles license removal
- `Dockerfile`: Defines the Docker image with Python and Playwright
- `docker-compose.yml`: Configures the container setup
- `requirements.txt`: Lists Python dependencies
- `entrypoint.sh`: Container startup script

## Logs

Logs are written to both console output and `steam_remover.log` file.

## Continuous Operation

By default, the application will:
1. Find and remove free licenses one by one
2. Wait between removals (to avoid rate limiting)
3. Continue scanning periodically even when no licenses are found
4. Send status updates via Telegram (if configured)

## Troubleshooting

- **Invalid Cookies**: If you see cookie errors, re-export your cookies and convert them again
- **Connection Issues**: Check your internet connection and Steam status
- **Container Crashes**: Check logs with `docker-compose logs`

## License

This project is for educational purposes only. Use at your own risk.

## Disclaimer

Automating interactions with Steam may violate their Terms of Service. This tool is provided as-is with no warranty. Use at your own discretion and risk.
