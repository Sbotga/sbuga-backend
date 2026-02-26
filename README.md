# The Most Sbuga Backend
Backend API for [sbuga.com](https://sbuga.com), a **WIP** website for minigames, tools, and data on the game Project SEKAI.

## Tech Stack

| Technology | Purpose |
|---|---|
| FastAPI | Backend framework |
| PostgreSQL | Database |
| Nginx | Reverse proxy |
| Cloudflare Turnstile | Bot protection |
| Cloudflare R2 | Asset storage |
| ffmpeg | Audio file converter |
| vgmstream | Decode .usm files |
| ChromeDriver + Selenium | SVG to PNG |

## Credits

- [YumYummity](https://github.com/YumYummity) - Lead developer
- [mos9527/sssekai](https://github.com/mos9527/sssekai) - Some of the game API interaction logic

## Hidden Code
Parts of this project, located under `pjsk_api/`, are hidden from the public as it contains sensitive code to interact with the official PJSK APIs. If you wish to get started on your own, check out sssekai (credited above).

## Running this project
1. Get a copy of the hidden code...
2. Fill out the config accordingly (setting up any external services as required).
3. Install all requirements into a virtual environment. (NOTE: NEEDS G++ COMPILER!)
4. Install vgmstream, ffmpeg, and ChromeDriver to path.
5. SBUGA!

Some download instructions for Ubuntu/Debian can be found below.

### G++ compiler
```bash
sudo apt install g++
```

### vgmstream & ffmpeg
```bash
# vgmstream
sudo apt install unzip -y
wget https://github.com/vgmstream/vgmstream/releases/download/VERSION GOES HERE/vgmstream-linux-cli.zip
unzip vgmstream-linux-cli.zip -d vgmstream
sudo mv vgmstream /usr/local/lib/vgmstream
sudo ln -s /usr/local/lib/vgmstream/vgmstream-cli /usr/local/bin/vgmstream-cli
# ffmpeg
sudo apt install ffmpeg -y
```

### Chromedriver
```bash
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install ./google-chrome-stable_current_amd64.deb
sudo apt install chromium-chromedriver
```

### Unidic (770mb)
RUN THIS AFTER INSTALLING REQUIREMENTS
```bash
python -m unidic download
```

## License

This project is licensed under the [MIT License](LICENSE).