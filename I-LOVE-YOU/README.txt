I Love You
JIN2 · @jin_22ee · 2026

------------------------------------------------------------
WHAT'S INSIDE
------------------------------------------------------------
  i_love_you.py      the full artwork. Run it and the heart appears in a window.
  sprites/           "I love you" in 114 languages, one picture per phrase
  requirements.txt   the Python libraries it needs (numpy, pygame-ce, opencv-python)
  HOW_IT_WORKS.txt   how the artwork is made, step by step
  LICENSE.txt        terms of use
  tools/             optional: the script that drew the phrase pictures

------------------------------------------------------------
HOW TO RUN
------------------------------------------------------------
1. Install Python 3.13 (https://www.python.org).
   Tip: a fresh virtual environment avoids clashes with an old 'pygame' install:
     python -m venv venv   then   venv\Scripts\activate   (macOS/Linux: source venv/bin/activate)
2. Open a terminal in this folder and install the libraries:

     pip install -r requirements.txt

3. Run the artwork:

     python i_love_you.py

Controls
  Space   pause / resume
  R       restart from the beginning
  S       save a screenshot (PNG) next to the file
  Esc     quit

The heart turns once every 10 seconds and keeps turning.
It aims for 30 fps; on an everyday laptop it may run slower.
On small or scaled screens the window shrinks to fit.

------------------------------------------------------------
TESTED ON
------------------------------------------------------------
  Tested:       Windows 11 + Python 3.13 (fresh virtual environment)
  Expected to work, not tested yet:
                Python 3.10 - 3.12, macOS, Linux

------------------------------------------------------------
PLEASE NOTE
------------------------------------------------------------
- This is the artwork itself, running live on your computer (not a video file).
- The phrases are pictures, so they look the same on every computer.
  To change them, edit PHRASES in tools/make_phrases.py and run it
  (it needs: pip install playwright, then: playwright install chromium).

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
