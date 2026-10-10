"""
تحميل .env مرة واحدة ومضمونة — بدون الاعتماد على ترتيب الاستيراد.
هذا بالضبط يصلح ثغرة حقيقية لقيتها بـ computer_sandbox.py القديم: كان
يفترض أن brain.py استُورد قبله فحمّل .env، فلو استُدعي لحاله ما يشوف
المفاتيح أبداً. أي ملف هنا يحتاج متغير بيئة يستورد هذا الملف أولاً.
"""

import os

from dotenv import load_dotenv

_ENV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"
)
load_dotenv(_ENV_PATH)
