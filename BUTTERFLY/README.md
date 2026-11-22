# BUTTERFLY

Butterfly · ASCII Code Art · JIN2, 2026

![BUTTERFLY](images/preview.gif)

## Artist's Note

Something knocks on the wall from the other side.
A hairline crack, then another hit, and another, until the glass gives way.
Butterflies slip out of the hole one by one and wander off, near and far, in and out of view.

| crack | break | flight |
|---|---|---|
| ![](images/01_crack.png) | ![](images/02_break.png) | ![](images/03_flight.png) |

## Technology

Python · NumPy · pygame-ce

## Creative Process

1. Wings: a forewing and a hindwing drawn as outlines, filled with points, brighter toward the body.
2. Flight: each wing beats on its own rhythm, the body dips on the downstroke and leans into turns.
3. Paths: twenty-two butterflies, each with its own home, depth and slow wandering loop that can leave the frame and come back.
4. Glass: the cracks only move when the wall is hit. Radial cracks fork as they run, round cracks join them, and on the last hit the center pieces drop out.
5. Dust: puffs on every hit, powder falling off the broken edge, and glitter shaken from the wings.

## Technical Concepts

Point-in-polygon sampling · perspective projection with depth ordering · random-walk crack paths
Impact timing with ease-out · per-cell hashing for texture · trail and glow pass

## Source Code

The full Python source is included in this folder.

```
pip install -r requirements.txt
python butterfly.py
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

---

Artist: JIN2 · Instagram [@jin_22ee](https://instagram.com/jin_22ee)
© 2026 JIN2. All rights reserved. Images and video in this repository may not be reused without permission.
