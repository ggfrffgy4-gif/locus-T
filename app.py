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
# Берется автоматически из переменной окружения (например, на Render или через set)
# ==============================================================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")


def get_wikipedia_campus_photos(uni_name):
  """Ищет до 8 фотографий кампуса вуза из Википедии."""
  headers = {"User-Agent": "LocusCampusAI/3.0 (student project)"}

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
    print(f"Ошибка поиска статьи: {e}")

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
          "Лаборатории",
      ]

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


def generate_detailed_fallback(uni_name):
  """Подробная база с реальными фактами на случай отсутствия API-ключа."""
  lowered = uni_name.lower()

  if "stanford" in lowered or "стэнфорд" in lowered:
    return {
        "location": "Пало-Альто / Станфорд, Калифорния, США",
        "overview": (
            "Stanford University — один из ведущих мировых исследовательских"
            " центров, стабильно занимающий топ-3 в мировых рейтингах QS и THE."
            " Кампус площадью более 33 кв. км является одним из самых больших в"
            " США, здесь обучается около 17 000 студентов. Университет стал"
            " колыбелью и научным двигателем Кремниевой долины."
        ),
        "atmosphere": (
            "Студенты живут в жилых домах и кооперативах, почти все передвигаются"
            " на велосипедах. Культура вуза пропитана духом технологических"
            " стартапов: проекты создаются прямо в общежитиях. Знаковые традиции"
            " — праздник 'Full Moon on the Quad' и эксцентричные выступления"
            " студенческого оркестра Leland Stanford Band."
        ),
        "history": (
            "Вуз основан в 1885 году сенатором Лилендом Стэнфордом и его"
            " супругой Джейн в память об умершем сыне. В середине XX века декан"
            " Фредерик Терман основал Стенфордский индустриальный парк, положив"
            " начало Кремниевой долине. С вузом связаны 85 нобелевских лауреатов"
            " и основатели компаний Google, HP, Nike, Netflix и Yahoo."
        ),
        "strengths": [
            "Computer Science & Artificial Intelligence (лаборатория SAIL)",
            "Graduate School of Business (GSB — №1 бизнес-школа)",
            "Инженерия, биоинженерия и робототехника",
            "Юриспруденция и медицинские исследования",
        ],
        "facts": [
            (
                "Если бы компании, созданные выпускниками Стэнфорда, образовали"
                " отдельную страну, её экономика вошла бы в топ-10 стран мира."
            ),
            (
                "Ларри Пейдж и Сергей Брин разработали первую версию поисковой"
                " системы Google в комнате стэнфордского общежития."
            ),
            (
                "У университета нет официального маскота, его символ —"
                " Стэнфордское Дерево (секвойя El Palo Alto)."
            ),
            (
                "87-метровая башня Гувера хранит редкие исторические архивы XX"
                " века и уникальный карильон из 48 колоколов."
            ),
        ],
        "admissions": {
            "exams": "SAT 1500-1570 / ACT 34-35, TOEFL 105+ / IELTS 8.0, GPA 3.9+",
            "documents": (
                "Common Application, развернутые эссе Стэнфорда, 2 рекомендации"
                " преподавателей, список внеучебных побед"
            ),
            "funding": (
                "Бесплатное обучение для семей с доходом менее $150,000/год,"
                " щедрая стипендиальная помощь"
            ),
            "insider_tip": (
                "Комиссия ищет 'Intellectual Vitality' — искреннюю страсть к"
                " созданию нового и исследовательскую инициативу."
            ),
        },
    }

  # Для всех остальных вузов
  return {
      "location": f"Кампус {uni_name}",
      "overview": (
          f"{uni_name} входит в число признанных академических центров,"
          " предлагая фундаментальные программы бакалавриата и магистратуры."
          " Университет объединяет сильные научно-исследовательские школы и"
          " привлекает студентов высоким уровнем трудоустройства выпускников."
      ),
      "atmosphere": (
          "Студенческая жизнь насыщена хакатонами, научными конференциями и"
          " клубами по интересам. На территории кампуса расположены современные"
          " коворкинги, лаборатории и развитая студенческая инфраструктура."
      ),
      "history": (
          f"{uni_name} имеет богатую историю становления и преемственности"
          " поколений. Выпускники вуза работают в ведущих технологических,"
          " финансовых и государственных институтах."
      ),
      "strengths": [
          "Информационные технологии и Software Engineering",
          "Инженерные науки и инновации",
          "Экономика, бизнес и аналитика",
          "Фундаментальные исследования",
      ],
      "facts": [
          (
              f"Выпускники {uni_name} успешно руководят крупными компаниями и"
              " исследовательскими центрами."
          ),
          (
              "Кампус сочетает академические традиции с ультрасовременным"
              " оборудованием и лабораториями."
          ),
          (
              "В университете регулярно проводятся ярмарки вакансий с участием"
              " международных работодателей."
          ),
          (
              "Библиотечные базы вуза предоставляют доступ к ключевым мировым"
              " научным изданиям (Scopus, IEEE)."
          ),
      ],
      "admissions": {
          "exams": (
              "IELTS 6.5–7.5, профильные тесты (ЕНТ/SAT/GRE) и высокий средний"
              " балл аттестата."
          ),
          "documents": (
              "Академический транскрипт, мотивационное письмо (Personal"
              " Statement), рекомендации."
          ),
          "funding": (
              "Государственные гранты, академические стипендии за высокие баллы"
              " и скидки от вуза."
          ),
          "insider_tip": (
              "Показывайте портфолио реальных проектов, олимпиадные достижения"
              " и лидерский опыт."
          ),
      },
  }


def get_ai_data(uni_name):
  """Генерирует профиль вуза через Gemini API или отдает резервные факты."""
  prompt = f"""
Ты международный эксперт по высшему образованию. 
Составь подробное, уникальное описание для университета "{uni_name}". 
НЕ пиши общие пустые фразы. Приводи ТОЛЬКО реальные факты, цифры, имена основателей, нобелевских лауреатов, названия кампусов, факультетов и студенческих традиций.

Ответь СТРОГО в формате валидного JSON со следующими полями на русском языке (без разметки markdown, только сырой JSON):
{{
  "location": "Точный город, Штат/Область, Страна",
  "overview": "Развернутое описание (4-5 предложений): мировой статус в QS/THE, площадь кампуса, сколько студентов учится, чем вуз знаменит.",
  "atmosphere": "Студенческая жизнь (4-5 предложений): жизнь в резиденциях, студенческие клубы, спорт и ежегодные традиции именно этого вуза.",
  "history": "История и наследие (4-5 предложений): точный год основания, основатели, ключевые вехи, изобретения и знаменитые выпускники.",
  "strengths": [
    "Сильный факультет/направление с пояснением",
    "Сильный факультет/направление с пояснением",
    "Сильный факультет/направление с пояснением",
    "Сильный факультет/направление с пояснением"
  ],
  "facts": [
    "Конкретный удивительный исторический или архитектурный факт",
    "Факт о знаменитых стартапах, компаниях или научных прорывах выпускников",
    "Необычная студенческая традиция или примета",
    "Факт о библиотеке, спорте или кампусе с реальными цифрами/деталями"
  ],
  "admissions": {{
    "exams": "Требования к экзаменам (IELTS/TOEFL, SAT/ACT/ЕНТ/GRE, минимальный GPA)",
    "documents": "Пакет документов (Personal Statement, резюме, рекомендации)",
    "funding": "Программы финансирования и стипендии (Need-blind, Болашак, Merit scholarships)",
    "insider_tip": "Инсайдерский совет: что больше всего ценится в кандидатах именно этого вуза"
  }}
}}
"""

  api_key = GEMINI_API_KEY.strip()

  if api_key and api_key != "ВАШ_КЛЮЧ_СЮДА":
    for model_name in [
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-2.0-flash",
    ]:
      try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.4,
                "response_mime_type": "application/json",
            },
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=15) as resp:
          res_data = json.loads(resp.read().decode("utf-8"))
          text_resp = res_data["candidates"][0]["content"]["parts"][0]["text"]

          cleaned = text_resp.strip()
          if cleaned.startswith("```"):
            cleaned = re.sub(
                r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE
            )
            cleaned = re.sub(r"\s*```$", "", cleaned)

          parsed_json = json.loads(cleaned.strip())
          print(f" Успешно получены факты от Gemini ({model_name})!")
          return parsed_json

      except Exception as e:
        print(f"⚠️ Ошибка Gemini ({model_name}): {e}")

  print(" Внимание: сработал резервный генератор фактов.")
  return generate_detailed_fallback(uni_name)


def get_google_maps_data(uni_name):
  query_param = urllib.parse.quote_plus(f"{uni_name} campus")
  return {
      "view_url": (
          f"[https://www.google.com/maps/search/?api=1&query=](https://www.google.com/maps/search/?api=1&query=){query_param}"
      ),
      "embed_url": (
          f"[https://maps.google.com/maps?q=](https://maps.google.com/maps?q=){query_param}&t=&z=15&ie=UTF8&iwloc=&output=embed"
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
  }

  search_uni = aliases.get(raw_query.lower(), raw_query)

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
      "admissions": ai_content.get("admissions", {}),
      "images": images,
      "maps": maps_info,
  })


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=8080, debug=True)
