import json
import os
import re
from flask import Flask, jsonify, render_template, request

try:
  import requests

  USE_REQUESTS = True
except ImportError:
  import urllib.request

  USE_REQUESTS = False

app = Flask(__name__)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()


def get_wikipedia_campus_photos(uni_name):
  clean = re.sub(
      r"\b(university|университет|институт)\b", "", uni_name, flags=re.I
  ).strip()
  url = f"https://en.wikipedia.org/w/api.php?action=query&generator=search&gsrsearch={clean}+campus&gsrlimit=5&prop=images&imlimit=25&format=json&utf8=1"
  photos = []
  try:
    headers = {"User-Agent": "LocusCampus/7.0"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=5) as r:
      data = json.loads(r.read().decode())
      pages = data.get("query", {}).get("pages", {})
      for _, p in pages.items():
        for img in p.get("images", []):
          t = img.get("title", "")
          if any(
              t.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png"]
          ) and not any(
              b in t.lower()
              for b in ["logo", "seal", "flag", "sign", "map", "diagram"]
          ):
            info_url = f"https://en.wikipedia.org/w/api.php?action=query&titles={urllib.parse.quote(t)}&prop=imageinfo&iiprop=url&iiurlwidth=800&format=json"
            req_info = urllib.request.Request(info_url, headers=headers)
            with urllib.request.urlopen(req_info, timeout=4) as ir:
              idata = json.loads(ir.read().decode())
              for _, ip in idata.get("query", {}).get("pages", {}).items():
                u = ip.get("imageinfo", [{}])[0].get("thumburl")
                if u:
                  photos.append({
                      "url": u,
                      "title": t.replace("File:", "")[:40],
                      "category": "Кампус",
                  })
          if len(photos) >= 8:
            return photos
  except Exception:
    pass
  return photos


def get_ai_data_from_gemini(uni_name):
  if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY отсутствует в Environment Variables!")

  prompt = (
      f"Детальный профиль университета '{uni_name}'. "
      "Ответь валидным JSON: location, overview, atmosphere, history, strengths"
      " (массив из 4 строк), facts (массив из 4 строк), admissions (объект с"
      " полями exams, documents, funding, insider_tip). Только факты и цифры."
  )
  payload = {
      "contents": [{"parts": [{"text": prompt}]}],
      "generationConfig": {
          "temperature": 0.3,
          "response_mime_type": "application/json",
      },
  }

  endpoint = (
      "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key="
      + GEMINI_API_KEY
  )
  raw_text = ""

  if USE_REQUESTS:
    res = requests.post(
        endpoint,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=20,
    )
    if res.status_code != 200:
      raise RuntimeError(f"Google HTTP {res.status_code}: {res.text[:120]}")
    raw_text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
  else:
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as res:
      raw_text = json.loads(res.read().decode())["candidates"][0]["content"][
          "parts"
      ][0]["text"]

  cleaned = re.sub(
      r"^```(?:json)?\s*|\s*```$", "", raw_text.strip(), flags=re.M
  )
  return json.loads(cleaned)


@app.route("/")
def home():
  return render_template("index.html")


@app.route("/search", methods=["POST"])
def search():
  query = (request.get_json() or {}).get("university", "").strip()
  if not query:
    return jsonify({"error": "Пустой запрос"}), 400

  aliases = {
      "nu": "Nazarbayev University",
      "ну": "Nazarbayev University",
      "mit": "MIT",
      "кбту": "Kazakh-British Technical University",
      "стэнфорд": "Stanford University",
  }
  target = aliases.get(query.lower(), query)

  try:
    ai = get_ai_data_from_gemini(target)
  except Exception as e:
    return jsonify({"error": f"Сбой ИИ: {str(e)}"}), 500

  q_url = urllib.parse.quote(f"{target} University campus")
  return jsonify({
      "university": target,
      "location": ai.get("location", ""),
      "overview": ai.get("overview", ""),
      "atmosphere": ai.get("atmosphere", ""),
      "history": ai.get("history", ""),
      "strengths": ai.get("strengths", []),
      "facts": ai.get("facts", []),
      "admissions": ai.get("admissions", {}),
      "images": get_wikipedia_campus_photos(target),
      "maps": {
          "embed_url": (
              f"https://maps.google.com/maps?q={q_url}&t=&z=15&ie=UTF8&iwloc=&output=embed"
          ),
          "direct_url": f"https://www.google.com/maps/search/?api=1&query={q_url}",
      },
  })


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 8080))
  app.run(host="0.0.0.0", port=port)
