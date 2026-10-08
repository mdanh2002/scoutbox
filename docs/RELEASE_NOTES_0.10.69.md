# ScoutBox 0.10.69

0.10.69 is a narrow packaging and chatbot-window-state patch on top of 0.10.68.

Changes:

- Compressed `docs/branding/scoutbox-brand-concept.png` while keeping it clear for normal on-screen display.
- Compressed `portal/static/portal/scoutbox-logo.png` while keeping it clear at the current rendered UI size.
- Changed release verification/package creation to avoid shipping `__pycache__` directories or `.pyc` files.
- Stopped the ScoutBox chatbot from persisting fullscreen state across page navigation.
- Closing the chatbot now exits fullscreen first so later opens do not randomly maximize after navigating around the app.

No unrelated behavior changes are intended.
