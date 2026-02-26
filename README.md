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

## Credits

- [YumYummity](https://github.com/YumYummity) - Lead developer
- [mos9527/sssekai](https://github.com/mos9527/sssekai) - Some of the game API interaction logic

## Hidden Code
Parts of this project, located under `pjsk_api/`, are hidden from the public as it contains sensitive code to interact with the official PJSK APIs. If you wish to get started on your own, check out sssekai (credited above).

## Running this project
1. Get a copy of the hidden code...
2. Fill out the config accordingly (setting up any external services as required).
3. Install all requirements into a virtual environment.
4. Install vgmstream and ffmpeg to path.
5. SBUGA!

## License

This project is licensed under the [MIT License](LICENSE).