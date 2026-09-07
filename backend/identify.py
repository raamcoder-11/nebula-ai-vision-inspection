"""Conservative Gemini component-verification gate."""
import base64
import json
import os
import requests

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
PROMPT = """You are the acceptance gate for a mechanical-component inspection tool. Decide whether the primary subject is a mechanical component (fastener, washer, nut, bracket, plate, gear, shaft, machined part, or similar). Reject notebooks, books, paper, packaging, food, animals, people, screens, scenery, and ambiguous images. A 87 mm x 50 mm visiting card may be present only as a reference. Return only JSON with is_mechanical_component, component_type, likely_standard, nominal_size_guess, identification_confidence, visible_defects, defect_confidence, and reject_reason. If unsure, set is_mechanical_component false. Never issue PASS/FAIL."""

def _fallback(reason, hint):
    return {"is_mechanical_component":False,"component_type":"unverified","likely_standard":"unknown","nominal_size_guess":"unknown","identification_confidence":0,"visible_defects":[],"defect_confidence":0,"reject_reason":"AI verification unavailable","identification_error":reason,"verification_hint":hint}

def _normalise(value):
    accepted=value.get("is_mechanical_component") is True
    defects=value.get("visible_defects") if isinstance(value.get("visible_defects"),list) else []
    return {"is_mechanical_component":accepted,"component_type":str(value.get("component_type") or ("unknown" if accepted else "unsupported image"))[:100],"likely_standard":str(value.get("likely_standard") or "unknown")[:100],"nominal_size_guess":str(value.get("nominal_size_guess") or "unknown")[:100],"identification_confidence":max(0,min(100,float(value.get("identification_confidence") or 0))),"visible_defects":[str(item)[:160] for item in defects[:10]],"defect_confidence":max(0,min(100,float(value.get("defect_confidence") or 0))),"reject_reason":str(value.get("reject_reason") or ("" if accepted else "Image is not a supported mechanical component"))[:200]}

def identify_component(image_bytes,api_key=None):
    api_key=api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:return _fallback("GEMINI_API_KEY is not configured", "GEMINI_API_KEY is missing or empty in backend/.env.")
    payload={"contents":[{"parts":[{"text":PROMPT},{"inline_data":{"mime_type":"image/jpeg","data":base64.b64encode(image_bytes).decode("ascii")}}]}],"generationConfig":{"temperature":0,"response_mime_type":"application/json"}}
    try:
        response=requests.post(f"{GEMINI_URL}?key={api_key}",json=payload,timeout=25)
        response.raise_for_status()
        text=response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        fence=chr(96)*3
        return _normalise(json.loads(text.replace(fence+"json","").replace(fence,"").strip()))
    except requests.Timeout:return _fallback("Gemini request timed out", "Gemini did not respond in time. Check the laptop internet connection and try again.")
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 0
        hints = {400:"Gemini rejected the request. Check the selected model name.",401:"The Gemini API key is invalid.",403:"The key is blocked or does not have Gemini API access.",404:"The configured Gemini model is unavailable. Use gemini-2.5-flash.",429:"Gemini quota or rate limit reached. Wait, then try again."}
        return _fallback(f"Gemini API returned HTTP {status}", hints.get(status, "Gemini returned an API error. Check the key and internet connection."))
    except Exception:return _fallback("Gemini verification failed", "Check the laptop internet connection, then restart Flask.")
