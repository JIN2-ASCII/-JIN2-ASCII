Birthday Cake
JIN2 · @jin_22ee · 2026

------------------------------------------------------------
WHAT'S INSIDE
------------------------------------------------------------
  birthday_cake.py   the full artwork. Run it and the cake builds itself in a window.
  requirements.txt   the Python libraries it needs (numpy, pygame-ce, pillow)
  HOW_IT_WORKS.txt   how the artwork is made, step by step
  LICENSE.txt        terms of use

------------------------------------------------------------
HOW TO RUN
------------------------------------------------------------
1. Install Python 3.13 (https://www.python.org).
   Tip: a fresh virtual environment avoids clashes with an old 'pygame' install:
     python -m venv venv   then   venv\Scripts\activate   (macOS/Linux: source venv/bin/activate)
2. Open a terminal in this folder and install the libraries:

     pip install -r requirements.txt

3. Run the artwork:

     python birthday_cake.py

Controls
  Space   pause / resume
  R       replay from the start
  S       save a screenshot (PNG) next to the file
  Esc     quit

It aims for 30 fps; on an everyday laptop expect around 20 fps.
If it feels slow, close other heavy programs.
On small or scaled screens the window shrinks to fit.

------------------------------------------------------------
TESTED ON
------------------------------------------------------------
  Tested:       Windows 11 + Python 3.13 (fresh virtual environment)
  Expected to work, not tested yet:
                Python 3.10 - 3.12, macOS, Linux
  Not working:  Python 3.15 preview (its NumPy build crashes)

The HAPPY BIRTHDAY letters use the Segoe UI Black font that comes with
Windows. On macOS or Linux a similar heavy font is used instead, so the
letter shapes may look slightly different.

------------------------------------------------------------
PLEASE NOTE
------------------------------------------------------------
- This is the artwork itself, running live on your computer (not a video file).

------------------------------------------------------------
RULES
------------------------------------------------------------
I share this code for you. Study it, change it, and use what you learn
to make your own ASCII art. That's what it's here for.

Please don't:
  - repost this code, or a big part of it, as your own
  - post my artwork (videos or images) as your own
  - sell it, or use it commercially without my permission
  - use it to train AI models

If you share something you made with it, a credit to @jin_22ee is
always appreciated. If you see my code or artwork posted as someone
else's, please report it and let me know.

Full terms: LICENSE.txt

Questions: Instagram @jin_22ee