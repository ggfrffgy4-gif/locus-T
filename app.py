import json
import os
import re
from flask import Flask, jsonify, render_template, request
import requests

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()


def get_wikipedia_campus_photos(uni_name):
  headers = {"User-Agent": "LocusCampusAI/6.0"}
  found_photos = []

  clean_name = re.sub(
      r"\b(university|университет|институт)\b", "", uni_name, flags=re.I
  ).strip()
  search_query = f"{clean_name} campus"

  bad_words = [
      "logo",
      "seal",
      "coat",
      "flag",
      "icon",
      "stub",
      "symbol",
      "sign",
      "map",
      "diagram",
      "chart",
  ]
  image_titles = []

  try:
    search_params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": search_query,
        "gsrlimit": 5,
        "prop": "images",
        "imlimit": 30,
        "format": "json",
        "utf8": 1,
    }
    r = requests.get(
        "https://en.wikipedia.org/w/api.php",
        params=search_params,
        headers=headers,
        timeout=6,
    )
    if r.status_code == 200:
      pages = r.json().get("query", {}).get("pages", {})
      for _, p in pages.items():
        for img in p.get("images", []):
          t = img.get("title", "")
          tl = t.lower()
          if any(tl.endswith(ext) for ext in [".jpg", ".jpeg", ".png"]):
            if not any(bad in tl for bad in bad_words) and t not in image_titles:
              image_titles.append(t)
  except Exception:
    pass

  for title in image_titles[:12]:
    if len(found_photos) >= 8:
      break
    try:
      info_params = {
          "action": "query",
          "titles": title,
          "prop": "imageinfo",
          "iiprop": "url",
          "iiurlwidth": 800,
          "format": "json",
      }
      r = requests.get(
          "https://en.wikipedia.org/w/api.php",
          params=info_params,
          headers=headers,
          timeout=4,
      )
      if r.status_code == 200:
        pages = r.json().get("query", {}).get("pages", {})
        for _, p in pages.items():
          info = p.get("imageinfo", [])
          if info:
            url = info[0].get("thumburl") or info[0].get("url")
            raw_title = (
                title.replace("File:", "")
                .replace(".jpg", "")
                .replace(".png", "")
                .replace(".jpeg", "")
            )
            raw_title = re.sub(r"[-_]+", " ", raw_title).strip()
            if url:
              found_photos.append({
                  "url": url,
                  "title": raw_title[:45],
                  "category": "Кампус",
              })
    except Exception:
      continue

  return found_photos


def get_ai_data_from_gemini(uni_name):
  if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY не задан в переменных Render!")

  prompt = f"""
Составь детальный профиль университета: "{uni_name}".
Приводи реальные факты: год основания, место в QS/THE, число студентов, имена выпускников, нобелевских лауреатов, названия общежитий и традиций, баллы экзаменов (SAT, IELTS, ЕНТ).

Ответь ИСКЛЮЧИТЕЛЬНО валидным JSON на русском языке (без разметки ```json):
{{
  "location": "Город, Страна",
  "overview": "Развернутый обзор (4-5 предложений) с цифрами и рейтингами.",
  "atmosphere": "Студенческая жизнь (4-5 предложений): традиции, спорт, быт.",
  "history": "История (4-5 предложений): основатели, даты, прорывы, выпускники.",
  "strengths": ["Факультет 1 с деталями", "Факультет 2 с деталями", "Факультет 3 с деталями", "Факультет 4 с деталями"],
  "facts": ["Факт 1 с цифрами", "Факт 2 о стартапах/науке", "Факт 3 о традициях", "Факт 4"],
  "admissions": {{
    "exams": "Баллы IELTS, SAT, GPA и требования",
    "documents": "Требования к эссе и портфолио",
    "funding": "Стипендии, гранты, покрытие расходов",
    "insider_tip": "Совет поступающим"
  }}
}}
"""

  payload = {
      "contents": [{"parts": [{"text": prompt}]}],
      "generationConfig": {
          "temperature": 0.35,
          "response_mime_type": "application/json",
      },
  }

  headers = {"Content-Type": "application/json"}
  last_err = ""

  models = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]

  for model in models:
    url = (
        "[https://generativelanguage.googleapis.com/v1beta/models/](https://generativelanguage.googleapis.com/v1beta/models/)"
        + model
        + ":generateContent?key="
        + GEMINI_API_KEY
    )
    try:
      response = requests.post(url, json=payload, headers=headers, timeout=20)
      if response.status_code == 200:
        data = response.json()
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        cleaned = re.sub(
            r"^```(?:json)?\s*|\s*```$", "", raw_text.strip(), flags=re.M
        )
        return json.loads(cleaned)
      else:
        last_err = f"Google HTTP {response.status_code}: {response.text[:120]}"
    except Exception as e:
      last_err = str(e)

  raise RuntimeError(last_err or "Нет ответа от моделей Gemini")


def get_map_urls(uni_name):
  q = requests.utils.quote(f"{uni_name} University campus")
  return {
      "embed_url": (
          f"[https://maps.google.com/maps?q=](https://maps.google.com/maps?q=){q}&t=&z=15&ie=UTF8&iwloc=&output=embed"
      ),
      "direct_url": f"[https://www.google.com/maps/search/?api=1&query=](https://www.google.com/maps/search/?api=1&query=){q}",
  }


@app.route("/")
def home():
  return render_template("index.html")


@app.route("/search", methods=["POST"])
def search():
  data = request.get_json() or {}
  raw_query = data.get("university", "").strip()
  if not raw_query:
    return jsonify({"error": "Введите название университета"}), 400

  aliases = {
      "nu": "Nazarbayev University",
      "ну": "Nazarbayev University",
      "назарбаев": "Nazarbayev University",
      "mit": "Massachusetts Institute of Technology",
      "мит": "Massachusetts Institute of Technology",
      "кбту": "Kazakh-British Technical University",
      "kbtu": "Kazakh-British Technical University",
      "казну": "Al-Farabi Kazakh National University",
      "kaznu": "Al-Farabi Kazakh National University",
      "стэнфорд": "Stanford University",
      "стенфорд": "Stanford University",
      "stanford": "Stanford University",
      "гарвард": "Harvard University",
      "harvard": "Harvard University",
      "оксфорд": "University of Oxford",
      "oxford": "University of Oxford",
      "кембридж": "University of Cambridge",
      "cambridge": "University of Cambridge",
  }

  search_uni = aliases.get(raw_query.lower(), raw_query)

  try:
    ai_content = get_ai_data_from_gemini(search_uni)
  except Exception as e:
    return jsonify({"error": f"Ошибка ИИ: {str(e)}"}), 500

  images = get_wikipedia_campus_photos(search_uni)
  maps_info = get_map_urls(search_uni)

  return jsonify({
      "university": search_uni,
      "location": ai_content.get("location", ""),
      "overview": ai_content.get("overview", ""),
      "atmosphere": ai_content.get("atmosphere", ""),
      "history": ai_content.get("history", ""),
      "strengths": ai_content.get("strengths", []),
      "facts": ai_content.get("facts", []),
      "admissions": ai_content.get("admissions", {}),
      "images": images,
      "maps": maps_info,
  })


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 8080))
  app.run(host="0.0.0.0", port=port)
