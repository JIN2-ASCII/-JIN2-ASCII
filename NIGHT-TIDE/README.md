# NIGHT TIDE

The sea at night · ASCII Code Art · JIN2, 2026

![NIGHT TIDE](images/preview.gif)

## Artist's Note

Dark water at night, with only a little light moving on it.
Waves roll in one after another, each with its own angle, size and strength, break into white foam and run up the sand.
The moon itself is not drawn, only its glitter on the water.

| rolling in | breaking | glitter |
|---|---|---|
| ![](images/01_rolling_in.png) | ![](images/02_breaking.png) | ![](images/03_glitter.png) |

## Technology

Python · NumPy · pygame-ce

## Creative Process

1. Camera: a view from the beach, each cell of the screen mapped to a point on the water.
2. Sea: many swells of different sizes and directions are layered into one moving surface.
3. Light: each tilted bit of water mirrors the night sky, and lit crests flash like moonlight.
4. Breakers: every wave rises, breaks into white foam, rushes in and slides back over the sand.
5. ASCII Rendering: the light on the water becomes letters, from faint to dense, in shades of blue.

## Technical Concepts

Gerstner waves · perspective projection · Fresnel reflection · procedural foam and spray
Level-of-detail filtering · character-based shading

## Source Code

The full Python source is free and included in this folder.

```
pip install -r requirements.txt
python night_tide.py
```

Space pause, R restart, S screenshot, Esc quit.
Rules for using this code:
I share this code for you. Study it, change it, and use what you learn to make your own ASCII art.
- Don't repost this code, or a big part of it, as your own.
- Don't post my artwork (videos or images) as your own.
- Don't sell it, or use it commercially without my permission.
- Don't use it with AI.

A credit to @jin_22ee is always appreciated. If you see my code or artwork posted as someone else's, please report it and let me know on Instagram [@jin_22ee](https://instagram.com/jin_22ee).

Full terms: [LICENSE.txt](LICENSE.txt)

If you'd like to support my work, the same code is also on [Payhip](https://payhip.com/b/TrI0Y).

---

Artist: JIN2 · Instagram [@jin_22ee](https://instagram.com/jin_22ee)
© 2026 JIN2. All rights reserved. Images and video in this repository may not be reused without permission.
