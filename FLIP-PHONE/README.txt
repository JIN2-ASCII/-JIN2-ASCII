Flip Phone
JIN2 · @jin_22ee · 2026

------------------------------------------------------------
WHAT'S INSIDE
------------------------------------------------------------
  flip_phone.py      the artwork. Run it and the phone rings in a window.
  requirements.txt   the two Python libraries it needs (numpy, pygame-ce)
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

     python flip_phone.py

Controls
  Space   pause / resume
  R       replay from the start
  S       save a screenshot (PNG) next to the file
  Esc     quit

The phone rings, flips open and keeps ringing; the piece starts over after 16 seconds.
It aims for 30 fps; on an everyday laptop it may run slower.
On small or scaled screens the window shrinks to fit.
The name on the screen uses the Impact font when it is installed, otherwise a bold font you have.

------------------------------------------------------------
TESTED ON
------------------------------------------------------------
  Tested:       Windows 11 + Python 3.13
  Expected to work, not tested yet:
                Python 3.10 - 3.12, macOS, Linux

------------------------------------------------------------
PLEASE NOTE
------------------------------------------------------------
- This is the artwork itself, drawn live in a window (not a video file).
- For personal projects. Please don't sell it or claim it as your own.
  See LICENSE.txt.

Questions: Instagram @jin_22ee
