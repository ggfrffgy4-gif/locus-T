import base64
import json
import os
import re
from flask import Flask, jsonify, render_template, request
import requests

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()


def get_wikipedia_campus_photos(uni_name):
  headers = {"User-Agent": "LocusCampusAI/10.0"}
  photos = []
  clean_name = re.sub(
      r"\b(university|университет|институт)\b", "", uni_name, flags=re.I
  ).strip()

  wiki_api = base64.b64decode(
      b"aHR0cHM6Ly9lbi53aWtpcGVkaWEub3JnL3cvYXBpLnBocA=="
  ).decode()

  try:
    r = requests.get(
        wiki_api,
        params={
            "action": "query",
            "generator": "search",
            "gsrsearch": f"{clean_name} campus",
            "gsrlimit": 5,
            "prop": "images",
            "imlimit": 20,
            "format": "json",
        },
        headers=headers,
        timeout=5,
    )
    pages = r.json().get("query", {}).get("pages", {})
    titles = []
    for _, p in pages.items():
      for img in p.get("images", []):
        t = img.get("title", "")
        tl = t.lower()
        if any(tl.endswith(ext) for ext in [".jpg", ".jpeg", ".png"]):
          if not any(
              bad in tl for bad in ["logo", "seal", "flag", "sign", "map"]
          ):
            titles.append(t)

    for t in titles[:6]:
      ir = requests.get(
          wiki_api,
          params={
              "action": "query",
              "titles": t,
              "prop": "imageinfo",
              "iiprop": "url",
              "iiurlwidth": 800,
              "format": "json",
          },
          headers=headers,
          timeout=4,
      )
      ipages = ir.json().get("query", {}).get("pages", {})
      for _, ip in ipages.items():
        u = ip.get("imageinfo", [{}])[0].get("thumburl")
        if u:
          name_clean = (
              t.replace("File:", "").replace(".jpg", "").replace(".png", "")
          )
          photos.append(
              {"url": u, "title": name_clean[:40], "category": "Кампус"}
          )
      if len(photos) >= 5:
        break
  except Exception:
    pass
  return photos


def get_ai_data_from_gemini(uni_name):
  if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY отсутствует в переменных окружения Render!")

  prompt = f"""
Составь детальный профиль университета "{uni_name}".
Ответь ТОЛЬКО валидным JSON на русском языке (без разметки ```json):
{{
  "location": "Город, Страна",
  "overview": "Обзор университета (3-4 предложения).",
  "atmosphere": "Студенческая жизнь и кампус (3-4 предложения).",
  "history": "История создания и факты (3-4 предложения).",
  "strengths": ["Факультет 1", "Факультет 2", "Факультет 3", "Факультет 4"],
  "facts": ["Факт 1", "Факт 2", "Факт 3", "Факт 4"],
  "admissions": {{
    "exams": "Требования к экзаменам",
    "documents": "Список документов",
    "funding": "Стипендии и гранты",
    "insider_tip": "Совет поступающим"
  }}
}}
"""
  payload = {
      "contents": [{"parts": [{"text": prompt}]}],
      "generationConfig": {
          "temperature": 0.3,
          "response_mime_type": "application/json",
      },
  }

  # Декодируем базовый домен из base64 — никаких ссылок в открытом тексте
  host = base64.b64decode(
      b"aHR0cHM6Ly9nZW5lcmF0aXZlbGFuZ3VhZ2UuZ29vZ2xlYXBpcy5jb20="
  ).decode()

  # Список моделей в порядке приоритета
  models = [
      "gemini-2.0-flash",
      "gemini-2.5-flash",
      "gemini-1.5-flash-latest",
      "gemini-1.5-pro-latest",
      "gemini-pro",
  ]

  last_err = ""
  for m in models:
    api_url = f"{host}/v1beta/models/{m}:generateContent"
    try:
      res = requests.post(
          api_url,
          params={"key": GEMINI_API_KEY},
          json=payload,
          headers={"Content-Type": "application/json"},
          timeout=18,
      )
      if res.status_code == 200:
        raw = res.json()["candidates"][0]["content"]["parts"][0]["text"]
        clean_json = re.sub(
            r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.M
        )
        return json.loads(clean_json)
      else:
        last_err = f"Google HTTP {res.status_code}: {res.text[:120]}"
    except Exception as e:
      last_err = str(e)

  raise RuntimeError(last_err or "Не удалось получить ответ от Gemini")


@app.route("/")
def home():
  return render_template("index.html")


@app.route("/search", methods=["POST"])
def search():
  try:
    data = request.get_json(force=True, silent=True) or {}
    raw_query = data.get("university", "").strip()
    if not raw_query:
      return jsonify({"error": "Введите название университета"}), 400

    aliases = {
        "nu": "Nazarbayev University",
        "ну": "Nazarbayev University",
        "mit": "MIT",
        "кбту": "Kazakh-British Technical University",
        "стэнфорд": "Stanford University",
        "стенфорд": "Stanford University",
    }
    uni = aliases.get(raw_query.lower(), raw_query)

    try:
      ai_data = get_ai_data_from_gemini(uni)
    except Exception as err:
      return jsonify({"error": f"Ошибка ИИ: {str(err)}"}), 200

    photos = get_wikipedia_campus_photos(uni)
    q_map = requests.utils.quote(f"{uni} University campus")

    return jsonify({
        "university": uni,
        "location": ai_data.get("location", ""),
        "overview": ai_data.get("overview", ""),
        "atmosphere": ai_data.get("atmosphere", ""),
        "history": ai_data.get("history", ""),
        "strengths": ai_data.get("strengths", []),
        "facts": ai_data.get("facts", []),
        "admissions": ai_data.get("admissions", {}),
        "images": photos,
        "maps": {
            "embed_url": (
                f"[https://maps.google.com/maps?q=](https://maps.google.com/maps?q=){q_map}&t=&z=15&ie=UTF8&iwloc=&output=embed"
            ),
            "direct_url": (
                f"[https://www.google.com/maps/search/?api=1&query=](https://www.google.com/maps/search/?api=1&query=){q_map}"
            ),
        },
    })
  except Exception as general_err:
    return jsonify({"error": f"Системный сбой: {str(general_err)}"}), 200


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 8080))
  app.run(host="0.0.0.0", port=port)
