import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# Ключ читается из настроек Render (Environment Variables) или локального окружения
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()


def get_wikipedia_campus_photos(uni_name):
  """Ищет реальные фотографии кампуса через Wikipedia API."""
  headers = {"User-Agent": "LocusCampusAI/5.0 (student campus project)"}
  found_photos = []

  # Очищаем запрос от дублирующих слов
  clean_name = re.sub(
      r"\b(university|университет|институт)\b", "", uni_name, flags=re.I
  ).strip()
  search_query = f"{clean_name} campus"

  search_url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
      "action": "query",
      "generator": "search",
      "gsrsearch": search_query,
      "gsrlimit": 5,
      "prop": "images",
      "imlimit": 40,
      "format": "json",
      "utf8": 1,
  })

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
      "signature",
      "portrait",
      "graph",
  ]
  image_titles = []

  try:
    req = urllib.request.Request(search_url, headers=headers)
    with urllib.request.urlopen(req, timeout=5) as resp:
      data = json.loads(resp.read().decode("utf-8"))
      pages = data.get("query", {}).get("pages", {})
      for _, p in pages.items():
        for img in p.get("images", []):
          t = img.get("title", "")
          tl = t.lower()
          if any(tl.endswith(ext) for ext in [".jpg", ".jpeg", ".png"]):
            if not any(bad in tl for bad in bad_words) and t not in image_titles:
              image_titles.append(t)
  except Exception as e:
    print(f"Ошибка поиска картинок: {e}")

  for title in image_titles[:15]:
    if len(found_photos) >= 10:
      break
    info_url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query",
        "titles": title,
        "prop": "imageinfo",
        "iiprop": "url",
        "iiurlwidth": 900,
        "format": "json",
    })
    try:
      req_info = urllib.request.Request(info_url, headers=headers)
      with urllib.request.urlopen(req_info, timeout=4) as resp:
        info_data = json.loads(resp.read().decode("utf-8"))
        for _, p in info_data.get("query", {}).get("pages", {}).items():
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
                  "title": raw_title[:50],
                  "category": "Кампус и архитектура",
              })
    except Exception:
      continue

  return found_photos


def get_ai_data_from_gemini(uni_name):
  """Генерирует уникальную информацию исключительно через нейросеть Gemini без заготовок."""
  if not GEMINI_API_KEY or GEMINI_API_KEY == "ВАШ_КЛЮЧ_СЮДА":
    raise ValueError(
        "Ключ GEMINI_API_KEY не задан! Добавьте его в Environment Variables в"
        " настройках Render или на компьютере."
    )

  prompt = f"""
Ты — аналитическая система по высшему образованию.
Составь детальный, уникальный и живой профиль университета: "{uni_name}".

КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО писать пустые шаблонные отговорки («один из ведущих вузов», «высокое качество знаний»).
Пиши ТОЛЬКО реальные факты:
- Конкретные цифры: год основания, место в рейтинге QS/THE, число студентов, площадь кампуса.
- Имена знаменитых выпускников, нобелевских лауреатов, основателей стартапов.
- Названия общежитий, студенческих клубов, спортивных команд и уникальных традиций.
- Точные баллы тестов для поступления (SAT, IELTS, GPA, ЕНТ) и конкретные гранты.

Ответь ИСКЛЮЧИТЕЛЬНО валидным JSON-объектом на русском языке (без разметки markdown ```json):
{{
  "location": "Город, Регион/Штат, Страна",
  "overview": "Развернутый обзор (4-5 предложений): мировой статус, позиции в QS/THE, масштабы кампуса, сколько студентов учится и чем университет известен миру.",
  "atmosphere": "Студенческая жизнь (4-5 предложений): как устроена жизнь в кампусе, реальные клубы, общежития, традиции и спортивные лиги.",
  "history": "История и наследие (4-5 предложений): точный год основания, кем создан, главные вехи, революционные открытия и известные выпускники.",
  "strengths": [
    "Направление 1 с точным названием факультета или лаборатории",
    "Направление 2 с точным названием факультета или лаборатории",
    "Направление 3 с точным названием факультета или лаборатории",
    "Направление 4 с точным названием факультета или лаборатории"
  ],
  "facts": [
    "Удивительный рекорд кампуса, библиотеки или архитектуры с конкретными цифрами",
    "Факт о созданных студентами стартапах, компаниях или научных прорывах",
    "Необычная студенческая традиция, примета или ритуал перед сессией",
    "Малоизвестный исторический или спортивный факт об этом вузе"
  ],
  "admissions": {{
    "exams": "Конкретные проходные баллы: IELTS/TOEFL, SAT/ACT/ЕНТ/GRE, минимальный GPA",
    "documents": "Что должно быть в заявке: темы эссе, портфолио, рекомендации",
    "funding": "Реальные гранты, стипендии (Need-based, Болашак, Merit) и покрытие расходов",
    "insider_tip": "Инсайдерский совет абитуриенту: на чем сделать акцент в портфолио для этого вуза"
  }}
}}
"""

  last_error = None
  # Пробуем доступные модели Gemini
  for model in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]:
    try:
      url = f"[https://generativelanguage.googleapis.com/v1beta/models/](https://generativelanguage.googleapis.com/v1beta/models/){model}:generateContent?key={GEMINI_API_KEY}"
      payload = {
          "contents": [{"parts": [{"text": prompt}]}],
          "generationConfig": {
              "temperature": 0.35,
              "response_mime_type": "application/json",
          },
      }
      req = urllib.request.Request(
          url,
          data=json.dumps(payload).encode("utf-8"),
          headers={"Content-Type": "application/json"},
      )

      with urllib.request.urlopen(req, timeout=20) as resp:
        res_data = json.loads(resp.read().decode("utf-8"))
        text_resp = res_data["candidates"][0]["content"]["parts"][0]["text"]

        # Очищаем от случайных markdown-обёрток
        cleaned = re.sub(
            r"^```(?:json)?\s*|\s*```$", "", text_resp.strip(), flags=re.M
        )
        data = json.loads(cleaned)
        print(f" Gemini успешно сгенерировал данные через модель {model}!")
        return data

    except urllib.error.HTTPError as http_err:
      err_text = http_err.read().decode("utf-8", errors="ignore")
      last_error = f"HTTP {http_err.code} от Google Gemini ({model}): {err_text}"
      print(f"⚠️ {last_error}")
    except Exception as e:
      last_error = f"Ошибка Gemini ({model}): {str(e)}"
      print(f"⚠️ {last_error}")

  # Если все модели не ответили — выбрасываем реальную ошибку
  raise RuntimeError(
      f"Не удалось получить ответ от ИИ: {last_error}. Проверьте правильность"
      " ключа GEMINI_API_KEY!"
  )


def get_map_urls(uni_name):
  """Формирует рабочие ссылки на Google Maps."""
  q = urllib.parse.quote_plus(f"{uni_name} University campus")
  return {
      # Надежная ссылка для iframe без блокировки
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
      "мгу": "Lomonosov Moscow State University",
      "оксфорд": "University of Oxford",
      "oxford": "University of Oxford",
      "кембридж": "University of Cambridge",
      "cambridge": "University of Cambridge",
  }

  search_uni = aliases.get(raw_query.lower(), raw_query)

  try:
    # Генерируем реальные данные через ИИ
    ai_content = get_ai_data_from_gemini(search_uni)
  except Exception as e:
    # Передаем точную ошибку на фронтенд, чтобы вы сразу видели, в чем проблема
    return (
        jsonify({
            "error": (
                f"Ошибка генерации ИИ: {str(e)}. Проверьте вкладку Environment"
                " Variables в Render!"
            )
        }),
        500,
    )

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
  app.run(host="0.0.0.0", port=8080, debug=True)
