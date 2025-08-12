from __future__ import annotations

import os
import datetime as dt
from typing import Any, Dict, List, Tuple

import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, url_for, send_from_directory


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
    )

    hyle_base_url = "https://hyle.appspot.com/palinsesto"

    def get_current_program_index(programs: List[Dict[str, str]]) -> int:
        now = dt.datetime.now()
        current_time = now.time()
        
        for i, program in enumerate(programs):
            if not program.get('time'):
                continue
                
            try:
                time_str = program['time']
                if ':' in time_str:
                    hour, minute = map(int, time_str.split(':'))
                    program_time = dt.time(hour, minute)
                    
                    if program_time <= current_time:
                        if i + 1 < len(programs) and programs[i + 1].get('time'):
                            next_time_str = programs[i + 1]['time']
                            if ':' in next_time_str:
                                next_hour, next_minute = map(int, next_time_str.split(':'))
                                next_program_time = dt.time(next_hour, next_minute)
                                if current_time < next_program_time:
                                    return i
                        else:
                            return i
            except (ValueError, IndexError):
                continue
        
        return 0

    def format_italian_date(date: dt.datetime) -> str:
        months = {
            1: 'Gennaio', 2: 'Febbraio', 3: 'Marzo', 4: 'Aprile',
            5: 'Maggio', 6: 'Giugno', 7: 'Luglio', 8: 'Agosto',
            9: 'Settembre', 10: 'Ottobre', 11: 'Novembre', 12: 'Dicembre'
        }
        days = {
            0: 'Lunedì', 1: 'Martedì', 2: 'Mercoledì', 3: 'Giovedì',
            4: 'Venerdì', 5: 'Sabato', 6: 'Domenica'
        }
        
        day_name = days[date.weekday()]
        day_num = date.day
        month_name = months[date.month]
        year = date.year
        
        return f"{day_name}, {day_num} {month_name} {year}"

    def scrape_hyle() -> Tuple[List[str], Dict[str, List[Dict[str, str]]]]:
        channels_order = [
            "Rai 1", "Rai 2", "Rai 3", "Rete 4",
            "Canale 5", "Italia 1", "LA7",
        ]

        try:
            mattina_html = requests.get(f"{hyle_base_url}/mattina", timeout=15).text
            pomeriggio_html = requests.get(f"{hyle_base_url}/pomeriggio", timeout=15).text
            sera_html = requests.get(f"{hyle_base_url}/serata", timeout=15).text
        except Exception:
            return [], {}

        def extract_uls(html_text: str) -> List[str]:
            try:
                soup = BeautifulSoup(html_text, "lxml")
                uls = soup.select("div.g3 > ul")
                return [ul.decode_contents() for ul in uls]
            except Exception:
                return []

        mattina_lists = extract_uls(mattina_html)
        pomeriggio_lists = extract_uls(pomeriggio_html)
        sera_lists = extract_uls(sera_html)

        programs_by_channel: Dict[str, List[Dict[str, str]]] = {}
        for idx, channel_name in enumerate(channels_order):
            try:
                mat = mattina_lists[idx] if idx < len(mattina_lists) else ""
                pom = pomeriggio_lists[idx] if idx < len(pomeriggio_lists) else ""
                ser = sera_lists[idx] if idx < len(sera_lists) else ""
            except Exception:
                mat = pom = ser = ""

            all_programs = []
            for ul_html in [mat, pom, ser]:
                if ul_html:
                    try:
                        soup = BeautifulSoup(f"<ul>{ul_html}</ul>", "lxml")
                        for li in soup.find_all("li"):
                            text = (li.get_text(" ", strip=True) or "").strip()
                            if text:
                                import re
                                m = re.match(r"^(\d{1,2}[:\.]\d{2})\s*(.*)$", text)
                                if m:
                                    time_part = m.group(1).replace(".", ":")
                                    title_part = m.group(2).strip()
                                    all_programs.append({"time": time_part, "title": title_part})
                                else:
                                    all_programs.append({"time": "", "title": text})
                    except Exception:
                        continue

            if all_programs:
                programs_by_channel[channel_name] = all_programs

        channels_present = [c for c in channels_order if c in programs_by_channel]
        return channels_present, programs_by_channel

    @app.get("/")
    def index():
        try:
            channel_filter = request.args.get("channel") or ""
            channels, programs_by_channel = scrape_hyle()

            active_channel = channel_filter if channel_filter in channels else (channels[0] if channels else "")

            logo_map = {}
            for channel_name in channels:
                key = (
                    channel_name.lower()
                    .replace(" ", "")
                    .replace(".", "")
                    .replace("+", "plus")
                    .replace("-", "")
                )
                candidate_png = f"img/{key}.png"
                logo_map[channel_name] = candidate_png

            current_program_index = 0
            if active_channel and active_channel in programs_by_channel:
                current_program_index = get_current_program_index(programs_by_channel[active_channel])

            current_date = dt.datetime.now()
            italian_date = format_italian_date(current_date)

            return render_template(
                "index.html",
                channels=channels,
                channel_filter=channel_filter,
                logo_map=logo_map,
                programs_by_channel=programs_by_channel,
                active_channel=active_channel,
                current_date=current_date,
                italian_date=italian_date,
                current_program_index=current_program_index,
            )
        except Exception:
            current_date = dt.datetime.now()
            italian_date = format_italian_date(current_date)
            return render_template(
                "index.html",
                channels=[],
                channel_filter="",
                logo_map={},
                programs_by_channel={},
                active_channel="",
                current_date=current_date,
                italian_date=italian_date,
                current_program_index=0,
            )

    @app.get("/manifest.webmanifest")
    def manifest() -> Any:
        response = send_from_directory(app.static_folder, "manifest.webmanifest")
        response.headers["Content-Type"] = "application/manifest+json"
        return response

    @app.get("/sw.js")
    def service_worker() -> Any:
        response = send_from_directory(app.static_folder, "sw.js")
        response.headers["Content-Type"] = "application/javascript"
        return response

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5001"))
    app.run(host="0.0.0.0", port=port, debug=True)


