# Nebula Vision Inspection

A smartphone-friendly Flask application for conservative 2-D inspection of one mechanical component next to an **edge-to-edge 150 mm ruler**.

## What is fixed

- OpenCV calibrates from the ruler's 150 mm long outer edge.
- An image is rejected when no card, no separate contour, or no verified mechanical component is found.
- Gemini verification fails closed: no API key or API failure cannot become PASS.
- PASS requires supplied nominal dimensions plus tolerance; otherwise an accepted image is REVIEW.
- The browser checks that the report response is an actual PDF before downloading it. JSON errors are shown on screen instead.
- Generated PDFs use the annotated inspection image.

## Prerequisites

Install Python 3.11 or 3.12 from https://www.python.org/downloads/windows/. During setup select **Add Python to PATH**. Install ngrok from https://ngrok.com/download only if testing the phone camera through an HTTPS tunnel.

## Windows setup

Open **Command Prompt** and run these commands. Replace the first path if you extracted the ZIP somewhere else.

```cmd
cd D:\nebula-vision-inspection\backend
py -3.12 -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

In Notepad, replace only `put_your_key_here` with your Gemini API key. Save and close it. The `.env` file belongs in `backend`, beside `.env.example`; never put it in `venv`, commit it, or share it.

Start the app:

```cmd
python app.py
```

Open http://localhost:5000 on the laptop.

## Phone camera testing

A phone browser normally requires HTTPS before it grants camera access. Keep Flask running, open a second Command Prompt, then run:

```cmd
ngrok config add-authtoken YOUR_NGROK_TOKEN
ngrok http 5000
```

ngrok is a separate Windows application, not a Python package and not part of the virtual environment. Open the displayed `https://...ngrok-free.app` URL on the phone.

## Inspection procedure

1. Put one flat mechanical component beside a ruler whose physical outer end-to-end length is exactly 150 mm; both must be in the same plane. A longer ruler with a 15 cm marking is not valid.
2. Use even lighting and photograph directly above the parts. Keep the whole ruler in frame.
3. Capture/upload the image. A notebook or other non-component must display **Inspection rejected**, not PASS.
4. Enter nominal length/width and tolerance when you need an automatic PASS/FAIL decision. Without them, the result deliberately remains REVIEW.
5. Download a report only after an accepted inspection. The browser verifies `application/pdf` before saving it.

## Important limits

This is a prototype, not certified metrology or QA equipment. Perspective, lens distortion, reflections, non-coplanar objects, thread pitch, depth, and hidden defects limit accuracy. Gemini’s defect output is an AI estimate, not ground truth.

## Optional deployment

For Render: push this clean folder to GitHub, choose root directory `backend`, use build command `pip install -r requirements.txt`, start command `gunicorn app:app`, and add `GEMINI_API_KEY` in Render’s environment-variable page. Do not upload `.env`.
