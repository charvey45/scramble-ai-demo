# Scramble AI Demo

`Scramble AI Demo` is a compact side-scrolling arcade game built with Python and `pygame`. It follows the same lightweight public-demo shape as `asteroids-ai-demo`: one main game file, generated sound effects, no external art or audio assets, and enough polish to be easy to run and inspect.

This repo is useful as both:

- a playable `Scramble`-style sample project
- a lightweight example of AI-assisted software delivery

## Why This Repo Exists

I wanted a second small public game repo that uses the same tooling and overall repository philosophy as `asteroids-ai-demo`, but with a different arcade design challenge. Instead of an arena shooter, this one focuses on the classic `Scramble` loop: surviving a scrolling terrain run, destroying ground targets, dropping bombs, and managing fuel.

The result is a project that is still intentionally small enough to understand quickly, but complete enough to demonstrate:

- building a second game on a consistent minimal framework
- turning a classic arcade reference into a clean standalone demo
- iterating toward a shareable public repository without introducing a heavy engine or asset pipeline

## Features

- Side-scrolling `Scramble`-style flight with terrain and cave sections
- Separate gun and bomb controls for air and ground threats
- Fuel depletion, fuel-tank pickups, score tracking, and lives
- Generated retro sound effects with no external asset files
- Title screen and game-over restart flow
- Persistent best score and sound settings
- Particle bursts and escalating waves

## Tech Notes

- Language: Python 3.11+
- Library: `pygame`
- Main entry point: [main.py](main.py)
- Local save file: `.scramble-save.json`

As with the reference repo, the core logic stays in a single file on purpose. That keeps the project easy to inspect in a portfolio or demo setting.

## Controls

- `Enter` or `Space`: start from the title screen or restart after game over
- `Left` / `Right`: move horizontally
- `Up` / `Down`: climb or dive
- `Space`: fire forward
- `X`: drop a bomb
- `M`: toggle sound on/off
- `-` / `+`: lower or raise volume
- `Esc`: quit

## Run Locally

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

## AI-Assisted Workflow

This project was built collaboratively with an AI coding agent. The human side set the target, chose the reference repo, and decided the level of fidelity. The agent accelerated implementation, repository setup, and documentation.

More detail is in [AI_COLLABORATION.md](AI_COLLABORATION.md).

## License

This project is available under the MIT License. See [LICENSE](LICENSE).
