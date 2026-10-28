#!/usr/bin/env python3
"""
UPSC CSE Prelims GS Paper-I PYQ Scraper → JSON

- Scrapes questions + options from a reliable public page (ClearIAS style).
- Optionally merges official answer key (from a dict or parsed PDF/text).
- If no official key is available for a question → correct_answer = null

Usage examples:
  python upsc_pyq_scraper.py --year 2015
  python upsc_pyq_scraper.py --year 2015 --key-file official_key_2015.txt
  python upsc_pyq_scraper.py --year 2015 --official-keys '{"1":"c","2":"a",...}'
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Known sources (extend this dict for more years)
# ---------------------------------------------------------------------------
SOURCES = {
    2014: {
        "questions_url": "https://www.clearias.com/upsc-prelims-2014-answer-key-solved-questions-gs-paper-1/",
        "official_key": {
            1:"b", 2:"a", 3:"a", 4:"d", 5:"c", 6:"a", 7:"a", 8:"c", 9:"c", 10:"b",
            11:"b", 12:"b", 13:"c", 14:"c", 15:"c", 16:"c", 17:"c", 18:"b", 19:"c", 20:"b",
            21:"b", 22:"b", 23:"a", 24:"d", 25:"c", 26:"b", 27:"d", 28:"b", 29:"d", 30:"c",
            31:"a", 32:"c", 33:"a", 34:"d", 35:"d", 36:"a", 37:"a", 38:"d", 39:"b", 40:"b",
            41:"a", 42:"b", 43:"c", 44:"c", 45:"b", 46:"a", 47:"c", 48:"c", 49:"d", 50:"a",
            51:"b", 52:"c", 53:"b", 54:"d", 55:"b", 56:"c", 57:"c", 58:"c", 59:"b", 60:"b",
            61:"c", 62:"a", 63:"c", 64:"c", 65:"b", 66:"d", 67:"c", 68:"b", 69:"d", 70:"b",
            71:"c", 72:"b", 73:"d", 74:"a", 75:"b", 76:"b", 77:"d", 78:"d", 79:"c", 80:"a",
            81:"b", 82:"b", 83:"b", 84:"a", 85:"c", 86:"a", 87:"d", 88:"c", 89:"c", 90:"d",
            91:"b", 92:"a", 93:"c", 94:"b", 95:"d", 96:"b", 97:"a", 98:"d", 99:"a", 100:"c",
        },
    },

    2015: {
        "questions_url": "https://www.clearias.com/upsc-prelims-2015-answer-key-solved-questions-of-gs-paper-1/",
        "official_key": {
            1:"c", 2:"a", 3:"b", 4:"a", 5:"b", 6:"d", 7:"c", 8:"b", 9:"b", 10:"a",
            11:"c", 12:"b", 13:"a", 14:"b", 15:"a", 16:"b", 17:"b", 18:"a", 19:"c", 20:"d",
            21:"d", 22:"c", 23:"c", 24:"b", 25:"c", 26:"d", 27:"b", 28:"b", 29:"c", 30:"d",
            31:"c", 32:"c", 33:"b", 34:"c", 35:"b", 36:"d", 37:"a", 38:"d", 39:"d", 40:"b",
            41:"b", 42:"d", 43:"a", 44:"d", 45:"c", 46:"b", 47:"c", 48:"b", 49:"a", 50:"c",
            51:"a", 52:"d", 53:"b", 54:"b", 55:"b", 56:"d", 57:"b", 58:"c", 59:"a", 60:"c",
            61:"d", 62:"b", 63:"c", 64:"c", 65:"b", 66:"b", 67:"d", 68:"a", 69:"a", 70:"d",
            71:"a", 72:"c", 73:"d", 74:"c", 75:"a", 76:"c", 77:"b", 78:"a", 79:"c", 80:"b",
            81:"b", 82:"d", 83:"d", 84:"c", 85:"c", 86:"c", 87:"c", 88:"a", 89:"b", 90:"b",
            91:"d", 92:"d", 93:"d", 94:"c", 95:"a", 96:"a", 97:"b", 98:"a", 99:"c", 100:"c",
        },
    },

    2016: {
        "questions_url": "https://www.clearias.com/upsc-prelims-2016-question-paper/",
        "official_key": {
            1:"b", 2:"c", 3:"c", 4:"b", 5:"c", 6:"b", 7:"d", 8:"c", 9:"c", 10:"b",
            11:"a", 12:"a", 13:"c", 14:"d", 15:"a", 16:"c", 17:"a", 18:"d", 19:"c", 20:"b",
            21:"b", 22:"b", 23:"a", 24:"b", 25:"d", 26:"c", 27:"b", 28:"d", 29:"a", 30:"c",
            31:"b", 32:"a", 33:"a", 34:"c", 35:"b", 36:"a", 37:"c", 38:"d", 39:"b", 40:"b",
            41:"d", 42:"a", 43:"c", 44:"d", 45:"a", 46:"c", 47:"a", 48:"a", 49:"a", 50:"b",
            51:"b", 52:"b", 53:"a", 54:"d", 55:"a", 56:"c", 57:"a", 58:"c", 59:"d", 60:"b",
            61:"a", 62:"b", 63:"d", 64:"d", 65:"b", 66:"b", 67:"b", 68:"d", 69:"b", 70:"a",
            71:"c", 72:"d", 73:"a", 74:"d", 75:"b", 76:"a", 77:"b", 78:"d", 79:"d", 80:"d",
            81:"a", 82:"b", 83:"c", 84:"c", 85:"b", 86:"b", 87:"d", 88:"c", 89:"b", 90:"d",
            91:"c", 92:"b", 93:"d", 94:"c", 95:"d", 96:"d", 97:"b", 98:"c", 99:"a", 100:"b",
        },
    },

    2017: {
        "questions_url": "https://www.clearias.com/upsc-prelims-2017-question-paper/",
        "official_key": {
            1:"d", 2:"c", 3:"a", 4:"a", 5:"a", 6:"b", 7:"b", 8:"c", 9:"a", 10:"b",
            11:"a", 12:"b", 13:"c", 14:"c", 15:"d", 16:"b", 17:"d", 18:"c", 19:"c", 20:"b",
            21:"c", 22:"b", 23:"a", 24:"b", 25:"d", 26:"d", 27:"a", 28:"d", 29:"c", 30:"b",
            31:"c", 32:"a", 33:"c", 34:"c", 35:"d", 36:"d", 37:"b", 38:"b", 39:"c", 40:"a",
            41:"d", 42:"a", 43:"a", 44:"a", 45:"d", 46:"c", 47:"a", 48:"a", 49:"b", 50:"d",
            51:"b", 52:"a", 53:"b", 54:"c", 55:"d", 56:"b", 57:"c", 58:"b", 59:"c", 60:"b",
            61:"b", 62:"d", 63:"d", 64:"b", 65:"b", 66:"b", 67:"b", 68:"b", 69:"a", 70:"a",
            71:"c", 72:"b", 73:"d", 74:"c", 75:"a", 76:"d", 77:"b", 78:"c", 79:"c", 80:"b",
            81:"a", 82:"a", 83:"a", 84:"c", 85:"d", 86:"c", 87:"b", 88:"a", 89:"b", 90:"d",
            91:"a", 92:"a", 93:"c", 94:"d", 95:"b", 96:"b", 97:"c", 98:"a", 99:"c", 100:"d",
        },
    },

    2018: {
        "questions_url": "https://www.clearias.com/upsc-prelims-2018-question-paper/",
        "official_key": {
            1:"b", 2:"d", 3:"c", 4:"b", 5:"a", 6:"c", 7:"a", 8:"d", 9:"c", 10:"a",
            11:"c", 12:"d", 13:"a", 14:"d", 15:"c", 16:"a", 17:"c", 18:"d", 19:"a", 20:"b",
            21:"b", 22:"b", 23:"a", 24:"b", 25:"b", 26:"d", 27:"d", 28:"a", 29:"a", 30:"a",
            31:"c", 32:"a", 33:"a", 34:"c", 35:"b", 36:"b", 37:"b", 38:"b", 39:"a", 40:"b",
            41:"c", 42:"d", 43:"c", 44:"b", 45:"c", 46:"b", 47:"c", 48:"c", 49:"c", 50:"d",
            51:"c", 52:"c", 53:"b", 54:"a", 55:"d", 56:"c", 57:"c", 58:"c", 59:"c", 60:"d",
            61:"a", 62:"d", 63:"b", 64:"b", 65:"a", 66:"b", 67:"d", 68:"d", 69:"c", 70:"d",
            71:"b", 72:"d", 73:"b", 74:"c", 75:"c", 76:"d", 77:"a", 78:"c", 79:"a", 80:"b",
            81:"b", 82:"b", 83:"b", 84:"d", 85:"a", 86:"b", 87:"d", 88:"c", 89:"b", 90:"c",
            91:"b", 92:"c", 93:"b", 94:"a", 95:"a", 96:"b", 97:"c", 98:"a", 99:"d", 100:"b",
        },
    },

    2019: {
        "questions_url": "https://www.clearias.com/upsc-prelims-2019-question-paper/",
        "official_key": {
            1:"d", 2:"b", 3:"c", 4:"a", 5:"c", 6:"d", 7:"c", 8:"a", 9:"d", 10:"a",
            11:"d", 12:"a", 13:"c", 14:"b", 15:"d", 16:"a", 17:"c", 18:"d", 19:"c", 20:"a",
            21:"a", 22:"a", 23:"a", 24:"b", 25:"d", 26:"d", 27:"a", 28:"d", 29:"c", 30:"a",
            31:"d", 32:"d", 33:"c", 34:"d", 35:"d", 36:"b", 37:"b", 38:"a", 39:"a", 40:"c",
            41:"d", 42:"d", 43:"b", 44:"b", 45:"b", 46:"c", 47:"a", 48:"a", 49:"a", 50:"b",
            51:"c", 52:"b", 53:"c", 54:"c", 55:"b", 56:"b", 57:"c", 58:"b", 59:"c", 60:"c",
            61:"b", 62:"a", 63:"d", 64:"b", 65:"b", 66:"c", 67:"d", 68:"a", 69:"a", 70:"a",
            71:"a", 72:"d", 73:"a", 74:"b", 75:"d", 76:"c", 77:"a", 78:"c", 79:"c", 80:"d",
            81:"d", 82:"a", 83:"a", 84:"d", 85:"d", 86:"d", 87:"a", 88:"c", 89:"b", 90:"b",
            91:"b", 92:"b", 93:"a", 94:"c", 95:"d", 96:"a", 97:"b", 98:"b", 99:"a", 100:"b",
        },
    },

    2020: {
        "questions_url": "https://www.clearias.com/upsc-prelims-2020-question-paper/",
        "official_key": {
            1:"b", 2:"b", 3:"d", 4:"d", 5:"b", 6:"d", 7:"d", 8:"d", 9:"a", 10:"c",
            11:"b", 12:"a", 13:"b", 14:"a", 15:"d", 16:"d", 17:"d", 18:"d", 19:"a", 20:"c",
            21:"c", 22:"b", 23:"a", 24:"c", 25:"c", 26:"a", 27:"d", 28:"a", 29:"a", 30:"a",
            31:"c", 32:"b", 33:"b", 34:"d", 35:"d", 36:"c", 37:"d", 38:"b", 39:"c", 40:"d",
            41:"d", 42:"d", 43:"d", 44:"d", 45:"b", 46:"a", 47:"c", 48:"d", 49:"a", 50:"d",
            51:"b", 52:"d", 53:"a", 54:"d", 55:"b", 56:"c", 57:"b", 58:"b", 59:"b", 60:"d",
            61:"c", 62:"a", 63:"d", 64:"b", 65:"a", 66:"b", 67:"a", 68:"c", 69:"d", 70:"c",
            71:"b", 72:"a", 73:"c", 74:"a", 75:"a", 76:"d", 77:"a", 78:"a", 79:"d", 80:"d",
            81:"a", 82:"a", 83:"d", 84:"a", 85:"a", 86:"a", 87:"a", 88:"d", 89:"c", 90:"d",
            91:"c", 92:"d", 93:"b", 94:"b", 95:"c", 96:"d", 97:"a", 98:"b", 99:"c", 100:"c",
        },
    },

    2021: {
        "questions_url": "https://www.clearias.com/upsc-prelims-2021-question-paper/",
        "official_key": {
            1:"c", 2:"b", 3:"b", 4:"a", 5:"b", 6:"d", 7:"a", 8:"a", 9:"d", 10:"d",
            11:"c", 12:"a", 13:"b", 14:"c", 15:"b", 16:"a", 17:"b", 18:"d", 19:"a", 20:"c",
            21:"c", 22:"b", 23:"d", 24:"a", 25:"b", 26:"c", 27:"c", 28:"c", 29:"a", 30:"d",
            31:"c", 32:"a", 33:"a", 34:"b", 35:"d", 36:"c", 37:"d", 38:"a", 39:"c", 40:"b",
            41:"b", 42:"b", 43:"a", 44:"c", 45:"a", 46:"c", 47:"d", 48:"b", 49:"a", 50:"b",
            51:"b", 52:"b", 53:"d", 54:"d", 55:"b", 56:"b", 57:"a", 58:"c", 59:"d", 60:"d",
            61:"c", 62:"b", 63:"b", 64:"b", 65:"c", 66:"c", 67:"b", 68:"c", 69:"a", 70:"b",
            71:"a", 72:"c", 73:"d", 74:"b", 75:"d", 76:"d", 77:"c", 78:"b", 79:"c", 80:None,
            81:"d", 82:"b", 83:"b", 84:"d", 85:"a", 86:"a", 87:"a", 88:"a", 89:"a", 90:"d",
            91:"b", 92:"b", 93:"b", 94:"d", 95:"d", 96:"d", 97:"d", 98:"c", 99:"b", 100:"d",
        },
    },

    2022: {
        "questions_url": "https://www.clearias.com/upsc-prelims-2022-question-paper/",
        "official_key": {
            1:"b", 2:"c", 3:"b", 4:"c", 5:"a", 6:"b", 7:"a", 8:"d", 9:"a", 10:"c",
            11:"b", 12:"b", 13:"b", 14:"b", 15:"b", 16:"b", 17:"d", 18:"c", 19:"d", 20:"a",
            21:"b", 22:"d", 23:"b", 24:"c", 25:"b", 26:"a", 27:"c", 28:"b", 29:"b", 30:"b",
            31:"d", 32:"d", 33:"d", 34:"c", 35:"b", 36:"d", 37:"d", 38:"c", 39:"b", 40:"c",
            41:"a", 42:"b", 43:"d", 44:"b", 45:"c", 46:"a", 47:"a", 48:"a", 49:"a", 50:"c",
            51:"c", 52:"b", 53:"d", 54:"b", 55:"b", 56:"c", 57:"b", 58:"d", 59:"d", 60:"d",
            61:"a", 62:"a", 63:"b", 64:"b", 65:"c", 66:"d", 67:"c", 68:"d", 69:"d", 70:"c",
            71:"c", 72:"a", 73:"a", 74:"b", 75:"c", 76:"a", 77:"a", 78:"d", 79:"d", 80:"a",
            81:"d", 82:"c", 83:"c", 84:"b", 85:"d", 86:"b", 87:"c", 88:"b", 89:"a", 90:"a",
            91:"b", 92:"b", 93:"b", 94:"a", 95:"a", 96:"a", 97:"d", 98:"d", 99:"d", 100:"a",
        },
    },

    2023: {
        "questions_url": "https://www.clearias.com/upsc-prelims-2023-question-paper/",
        "official_key": {
            1:"b", 2:"a", 3:"b", 4:"a", 5:"d", 6:"d", 7:"c", 8:"a", 9:"d", 10:"d",
            11:"c", 12:"c", 13:"a", 14:"b", 15:"c", 16:"d", 17:"a", 18:"c", 19:"b", 20:"d",
            21:"d", 22:"a", 23:"a", 24:"a", 25:"b", 26:"c", 27:"c", 28:"c", 29:"b", 30:"c",
            31:"c", 32:"a", 33:"c", 34:"a", 35:"a", 36:"d", 37:"c", 38:"c", 39:"b", 40:"c",
            41:"a", 42:"b", 43:"b", 44:"d", 45:"d", 46:"b", 47:"b", 48:"a", 49:"c", 50:"d",
            51:"c", 52:"d", 53:"c", 54:"c", 55:"b", 56:"a", 57:"d", 58:"d", 59:"c", 60:"c",
            61:"a", 62:"c", 63:"d", 64:"d", 65:"c", 66:"d", 67:"a", 68:"c", 69:"a", 70:"a",
            71:"b", 72:"a", 73:"d", 74:"b", 75:"b", 76:"c", 77:"b", 78:"d", 79:"c", 80:"b",
            81:"a", 82:"b", 83:"a", 84:"d", 85:"c", 86:"c", 87:"c", 88:"d", 89:"a", 90:"a",
            91:"c", 92:"c", 93:"d", 94:"c", 95:"b", 96:"b", 97:"a", 98:"d", 99:"c", 100:"c",
        },
    },

    2024: {
        "questions_url": "https://www.clearias.com/upsc-prelims-2024-question-paper/",
        "official_key": {
            1:"d", 2:"a", 3:"d", 4:"a", 5:"c", 6:"b", 7:"b", 8:"b", 9:"b", 10:"b",
            11:"a", 12:"a", 13:"d", 14:"c", 15:"d", 16:"b", 17:"d", 18:"b", 19:"c", 20:None,
            21:"c", 22:"a", 23:"d", 24:"d", 25:"a", 26:"d", 27:"d", 28:"a", 29:"c", 30:None,
            31:"b", 32:"d", 33:"a", 34:"b", 35:"d", 36:"a", 37:"d", 38:"c", 39:"d", 40:"c",
            41:"d", 42:"c", 43:"d", 44:"d", 45:"b", 46:"c", 47:"b", 48:"c", 49:"d", 50:"a",
            51:"a", 52:None, 53:"d", 54:"b", 55:"b", 56:"a", 57:None, 58:"b", 59:"a", 60:"c",
            61:"d", 62:"a", 63:"c", 64:"b", 65:"b", 66:"a", 67:"a", 68:"c", 69:"d", 70:"a",
            71:"d", 72:"a", 73:"b", 74:"d", 75:"c", 76:"d", 77:"d", 78:"c", 79:"a", 80:"c",
            81:"c", 82:"d", 83:"c", 84:"b", 85:"b", 86:"d", 87:"b", 88:"a", 89:"c", 90:"d",
            91:"a", 92:"d", 93:"a", 94:"b", 95:"c", 96:"c", 97:"d", 98:"d", 99:"b", 100:"b",
        },
    },

    2025: {
        "questions_url": "https://www.clearias.com/upsc-prelims-2025-question-paper/",
        "official_key": {
            1:"c", 2:"d", 3:"b", 4:"b", 5:"b", 6:"c", 7:"a", 8:"a", 9:"a", 10:"a",
            11:"c", 12:"a", 13:"b", 14:"a", 15:"b", 16:"c", 17:"c", 18:"d", 19:"c", 20:"c",
            21:"c", 22:"d", 23:"a", 24:"d", 25:"c", 26:"c", 27:"a", 28:"b", 29:"c", 30:"c",
            31:"c", 32:"d", 33:"c", 34:"b", 35:"b", 36:"b", 37:"b", 38:"b", 39:"b", 40:"b",
            41:"c", 42:"b", 43:"c", 44:"c", 45:"b", 46:"c", 47:"c", 48:"d", 49:"d", 50:"b",
            51:"c", 52:"c", 53:"b", 54:"a", 55:"c", 56:"b", 57:"d", 58:"d", 59:"d", 60:"a",
            61:"d", 62:"a", 63:"d", 64:"b", 65:"a", 66:"a", 67:"d", 68:"c", 69:"c", 70:"d",
            71:"b", 72:"c", 73:"b", 74:"a", 75:"c", 76:"d", 77:"a", 78:"a", 79:"c", 80:"d",
            81:"b", 82:"b", 83:"a", 84:"b", 85:"a", 86:"a", 87:"c", 88:"d", 89:"d", 90:"a",
            91:"c", 92:"d", 93:"c", 94:"d", 95:"c", 96:"b", 97:"c", 98:"a", 99:"c", 100:"b",
        },
    },

    2026: {
        "questions_url": "https://www.upsc.gov.in/examinations/Civil%20Services%20%28Preliminary%29%20Examination%2C%202026",
        "official_key": {
            1:"d", 2:"a", 3:"c", 4:"b", 5:"b", 6:"a", 7:"d", 8:"a", 9:"c", 10:"c",
            11:"d", 12:"a", 13:"c", 14:"b", 15:"b", 16:"b", 17:"a", 18:"d", 19:"d", 20:"b",
            21:"b", 22:"b", 23:"d", 24:"d", 25:"c", 26:"c", 27:"a", 28:"d", 29:"c", 30:"b",
            31:"a", 32:"b", 33:"b", 34:"b", 35:"b", 36:"b", 37:"c", 38:"b", 39:"b", 40:"c",
            41:"c", 42:"b", 43:"c", 44:"b", 45:"b", 46:"c", 47:"b", 48:"b", 49:"c", 50:"b",
            51:"c", 52:"a", 53:"b", 54:"d", 55:"b", 56:"b", 57:"a", 58:"c", 59:"d", 60:"a",
            61:"d", 62:"d", 63:"a", 64:None, 65:"d", 66:"a", 67:"b", 68:"a", 69:"c", 70:"a",
            71:"b", 72:"c", 73:"d", 74:"b", 75:"c", 76:"c", 77:"b", 78:"b", 79:"c", 80:"c",
            81:"c", 82:"a", 83:"c", 84:"a", 85:"a", 86:"c", 87:"a", 88:"c", 89:"c", 90:"d",
            91:"a", 92:"c", 93:"b", 94:"b", 95:"a", 96:"c", 97:"c", 98:"d", 99:"a", 100:"a",
        },
    },
}

def fetch_html(url: str, timeout: int = 30) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; UPSC-PYQ-Scraper/1.0; educational use)"
    }
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def parse_questions(html: str) -> List[dict]:
    """Extract numbered questions and (a)(b)(c)(d) options from page text."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator="\n")

    pattern = re.compile(
        r"Q\.\s*(\d+)\.\s*(.+?)(?=Q\.\s*\d+\.|$)",
        re.DOTALL | re.IGNORECASE,
    )
    matches = pattern.findall(text)

    questions = []
    seen = set()

    for qno_str, body in matches:
        qno = int(qno_str)
        if qno < 1 or qno > 100 or qno in seen:
            continue
        seen.add(qno)

        body = body.strip()

        opt_pat = re.compile(
            r"\(([a-d])\)\s*(.+?)(?=\s*\([a-d]\)|\bAns\b|\bSolution\b|$)",
            re.DOTALL | re.IGNORECASE,
        )
        opts = opt_pat.findall(body)
        options = {
            letter.lower(): re.sub(r"\s+", " ", opt_text).strip()
            for letter, opt_text in opts
        }

        q_text = re.split(r"\(a\)", body, maxsplit=1, flags=re.I)[0]
        q_text = re.sub(r"\s+", " ", q_text).strip()
        q_text = re.sub(r"(?i)\s*Select the correct answer.*$", "", q_text).strip()

        if not q_text or not options:
            continue

        questions.append(
            {
                "number": qno,
                "question": q_text,
                "options": options,
            }
        )

    questions.sort(key=lambda x: x["number"])
    return questions


def load_official_key(
    year: int,
    key_file: Optional[Path] = None,
    key_json: Optional[str] = None,
) -> Dict[int, str]:
    """
    Priority:
      1. --official-keys JSON string
      2. --key-file (one line per "QNO LETTER")
      3. Built-in SOURCES[year]["official_key"]
    """
    if key_json:
        raw = json.loads(key_json)
        return {int(k): str(v).lower().strip() for k, v in raw.items()}

    if key_file and key_file.exists():
        key: Dict[int, str] = {}
        for line in key_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r"(?:Q\.?\s*)?(\d+)\s*[:=\s]\s*([a-dA-D])", line)
            if m:
                key[int(m.group(1))] = m.group(2).lower()
        return key

    src = SOURCES.get(year, {})
    return {int(k): str(v).lower() for k, v in src.get("official_key", {}).items()}


def merge_answers(
    questions: List[dict], official_key: Dict[int, str]
) -> List[dict]:
    """Add correct_answer field (letter or null)."""
    for q in questions:
        ans = official_key.get(q["number"])
        if ans and ans in "abcd":
            q["correct_answer"] = ans
        else:
            q["correct_answer"] = None
    return questions


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape UPSC Prelims GS-I PYQs → JSON with optional official key"
    )
    parser.add_argument("--year", type=int, default=2015, help="Exam year (default 2015)")
    parser.add_argument("--url", type=str, default=None, help="Override questions page URL")
    parser.add_argument(
        "--key-file",
        type=Path,
        default=None,
        help="Text file with official answers (one per line: 1 c)",
    )
    parser.add_argument(
        "--official-keys",
        type=str,
        default=None,
        help='JSON string of answers, e.g. \'{"1":"c","2":"a"}\'',
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON path (default: upsc_prelims_<year>_pyq.json)",
    )
    args = parser.parse_args()

    year = args.year
    src = SOURCES.get(year, {})
    url = args.url or src.get("questions_url")
    if not url:
        print(
            f"No known source URL for year {year}. Pass --url or add entry to SOURCES.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Fetching questions for {year} from:\n  {url}")
    html = fetch_html(url)
    questions = parse_questions(html)
    print(f"Parsed {len(questions)} questions")

    official_key = load_official_key(year, args.key_file, args.official_keys)
    print(f"Official key entries available: {len(official_key)}")

    questions = merge_answers(questions, official_key)

    answered = sum(1 for q in questions if q["correct_answer"] is not None)
    print(f"Questions with correct_answer set: {answered}/{len(questions)}")

    result = {
        "exam": f"UPSC Civil Services (Preliminary) Examination {year}",
        "paper": "General Studies Paper-I",
        "year": year,
        "source": url,
        "total_questions": len(questions),
        "questions_with_official_key": answered,
        "questions": questions,
    }

    out_path = args.output or Path(f"upsc_prelims_{year}_pyq.json")
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Saved → {out_path.resolve()}")


if __name__ == "__main__":
    main()