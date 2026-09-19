import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# ==============================================================================
# НАСТРОЙКА КЛЮЧА GEMINI API:
# Можно передать через переменную окружения GEMINI_API_KEY
# либо напрямую вписать строкой вместо os.environ.get(...)
# ==============================================================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")


def get_wikipedia_campus_photos(uni_name):
  """Ищет и возвращает до 8 фотографий кампуса вуза из Википедии."""
  headers = {"User-Agent": "LocusCampusAI/3.0 (student project)"}

  # Формируем поисковый запрос без повторения слова "university"
  query_clean = uni_name.strip()
  if "university" not in query_clean.lower():
    search_term = f"{query_clean} University"
  else:
    search_term = query_clean

  search_url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
      "action": "query",
      "list": "search",
      "srsearch": search_term,
      "format": "json",
      "utf8": 1,
  })

  page_title = search_term
  try:
    req = urllib.request.Request(search_url, headers=headers)
    with urllib.request.urlopen(req, timeout=5) as resp:
      data = json.loads(resp.read().decode("utf-8"))
      results = data.get("query", {}).get("search", [])
      if results:
        page_title = results[0]["title"]
  except Exception as e:
    print(f"Ошибка поиска страницы Википедии: {e}")

  # Запрашиваем изображения из найденной статьи
  images_url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
      "action": "query",
      "titles": page_title,
      "prop": "images",
      "imlimit": 35,
      "format": "json",
      "utf8": 1,
  })

  found_photos = []
  try:
    req = urllib.request.Request(images_url, headers=headers)
    with urllib.request.urlopen(req, timeout=5) as resp:
      data = json.loads(resp.read().decode("utf-8"))
      pages = data.get("query", {}).get("pages", {})
      image_titles = []

      # Фильтруем логотипы, гербы, иконки и карты
      bad_keywords = [
          "logo",
          "seal",
          "coat of arms",
          "flag",
          "icon",
          "stub",
          "symbol",
          "sign",
          "map",
          "diagram",
          "chart",
      ]

      for _, p in pages.items():
        for img in p.get("images", []):
          t = img.get("title", "")
          lower_t = t.lower()
          if any(
              lower_t.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]
          ):
            if not any(bad in lower_t for bad in bad_keywords):
              image_titles.append(t)

      categories = [
          "Главный корпус",
          "Архитектура",
          "Студенческая жизнь",
          "Библиотека",
          "Инфраструктура",
          "Кампус",
          "Лаборатории и наука",
      ]

      # Загружаем прямые ссылки на превью изображений
      for idx, img_t in enumerate(image_titles[:12]):
        if len(found_photos) >= 8:
          break

        info_url = (
            "https://en.wikipedia.org/w/api.php?"
            + urllib.parse.urlencode({
                "action": "query",
                "titles": img_t,
                "prop": "imageinfo",
                "iiprop": "url",
                "iiurlwidth": 900,
                "format": "json",
            })
        )
        try:
          req_info = urllib.request.Request(info_url, headers=headers)
          with urllib.request.urlopen(req_info, timeout=4) as img_resp:
            img_data = json.loads(img_resp.read().decode("utf-8"))
            img_pages = img_data.get("query", {}).get("pages", {})
            for _, ipage in img_pages.items():
              info_list = ipage.get("imageinfo", [])
              if info_list:
                thumb_url = info_list[0].get("thumburl") or info_list[0].get(
                    "url"
                )
                clean_name = (
                    img_t.replace("File:", "")
                    .replace(".jpg", "")
                    .replace(".png", "")
                    .replace(".jpeg", "")
                )
                if thumb_url:
                  found_photos.append({
                      "url": thumb_url,
                      "title": clean_name[:50],
                      "category": categories[idx % len(categories)],
                  })
        except Exception:
          continue
  except Exception as e:
    print(f"Ошибка загрузки изображений: {e}")

  return found_photos


def get_ai_data(uni_name):
  """Генерирует развернутое описание, факты и сильные стороны вуза с помощью Gemini."""
  prompt = f"""
Ты международный эксперт по высшему образованию.
Составь подробное, живое и структурированное описание для университета: "{uni_name}".
Ответ должен быть строго в формате валидного JSON со следующими полями на русском языке:
{{
  "location": "Город, Страна",
  "overview": "Развернутое общее описание (4-5 предложений): мировой статус, репутация, масштабы кампуса и миссия вуза.",
  "atmosphere": "Описание студенческой жизни (4-5 предложений): студенческий вайб, клубы, традиции, условия в общежитиях и учебная среда.",
  "history": "История и наследие (4-5 предложений): год и предпосылки основания, ключевые вехи, выдающиеся выпускники или открытия.",
  "strengths": [
    "Сильное направление или факультет 1",
    "Сильное направление или факультет 2",
    "Сильное направление или факультет 3",
    "Сильное направление или факультет 4"
  ],
  "facts": [
    "Интересный факт о студенческих традициях или особенностях кампуса",
    "Факт о знаменитых выпускниках, технологических стартапах или Нобелевских лауреатах",
    "Необычный рекорд, архитектурная деталь или студенческая примета",
    "Факт о библиотечных фондах, спортивных победах или музейных коллекциях"
  ]
}}
"""

  if GEMINI_API_KEY and GEMINI_API_KEY != "ВАШ_КЛЮЧ_СЮДА":
    try:
      url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
      payload = {
          "contents": [{"parts": [{"text": prompt}]}],
          "generationConfig": {"response_mime_type": "application/json"},
      }
      req = urllib.request.Request(
          url,
          data=json.dumps(payload).encode("utf-8"),
          headers={"Content-Type": "application/json"},
      )
      with urllib.request.urlopen(req, timeout=12) as resp:
        res_data = json.loads(resp.read().decode("utf-8"))
        text_resp = res_data["candidates"][0]["content"]["parts"][0]["text"]
        cleaned_text = re.sub(
            r"^```json\s*|\s*```$", "", text_resp.strip(), flags=re.MULTILINE
        )
        return json.loads(cleaned_text)
    except Exception as e:
      print(f"Ошибка вызова Gemini API: {e}")

  # Качественные резервные данные, если ключ API отсутствует или недоступен
  return {
      "location": "Уточняется",
      "overview": (
          f"{uni_name} — признанный мировой лидер высшего образования,"
          " предлагающий передовые академические программы и сильную научную"
          " базу. Университет привлекает студентов со всех уголков планеты"
          " благодаря авторитетному профессорско-преподавательскому составу и"
          " тесной интеграции с передовыми индустриями."
      ),
      "atmosphere": (
          "В кампусе бурлит насыщенная студенческая жизнь: действуют десятки"
          " клубов по интересам, проводятся хакатоны, научные симпозиумы и"
          " культурные вечера. Общежития и зоны отдыха создают идеальные"
          " условия для учебы, нетворкинга и запуска совместных проектов."
      ),
      "history": (
          f"{uni_name} обладает богатой историей и выдающимся наследием. На"
          " протяжении своей деятельности вуз воспитал плеяду всемирно известных"
          " ученых, предпринимателей и общественных деятелей, оказавших"
          " фундаментальное влияние на мировое развитие."
      ),
      "strengths": [
          "Компьютерные науки, AI и IT",
          "Инженерия и передовые технологии",
          "Бизнес, финансы и предпринимательство",
          "Биомедицина и фундаментальные исследования",
      ],
      "facts": [
          f"Выпускники и преподаватели {uni_name} регулярно отмечаются"
          " престижнейшими международными наградами.",
          "Кампус объединяет в себе историческую архитектуру с ультрасовременными"
          " исследовательскими лабораториями.",
          "В университете существуют давние традиции и приметы, передающиеся от"
          " курса к курсу уже много поколений.",
          "Университет активно сотрудничает с ведущими глобальными корпорациями"
          " и венчурными фондами.",
      ],
  }


def get_google_maps_data(uni_name):
  """Формирует ссылки и embed-код Google Maps для отображения кампуса."""
  query_param = urllib.parse.quote_plus(f"{uni_name} campus")
  return {
      "view_url": (
          f"https://www.google.com/maps/search/?api=1&query={query_param}"
      ),
      "embed_url": (
          f"https://maps.google.com/maps?q={query_param}&t=&z=15&ie=UTF8&iwloc=&output=embed"
      ),
  }


@app.route("/")
def home():
  return render_template("index.html")


@app.route("/search", methods=["POST"])
def search():
  data = request.get_json() or {}
  raw_query = data.get("university", "").strip()
  if not raw_query:
    return jsonify({"error": "Пустой запрос"}), 400

  # Словарь синонимов и распространенных сокращений
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

  # Сбор всех блоков информации
  ai_content = get_ai_data(search_uni)
  images = get_wikipedia_campus_photos(search_uni)
  maps_info = get_google_maps_data(search_uni)

  return jsonify({
      "university": search_uni,
      "location": ai_content.get("location", ""),
      "overview": ai_content.get("overview", ""),
      "atmosphere": ai_content.get("atmosphere", ""),
      "history": ai_content.get("history", ""),
      "strengths": ai_content.get("strengths", []),
      "facts": ai_content.get("facts", []),
      "images": images,
      "maps": maps_info,
  })


if __name__ == "__main__":
  # Запуск локального сервера
  app.run(host="0.0.0.0", port=8080, debug=True)