# استضافة دائمة لـagent_os4/web_chat.py — راجع agent_os4/README.md قسم
# "الشات الدائم على الإنترنت" لشرح كامل وكيفية النشر (Fly.io).
#
# عمداً بلا Playwright/Chromium هنا — صورة أخف وأوثق على آلة صغيرة
# دائمة التشغيل (512mb)؛ Chromium وحده يستهلك 200+ MB عند التشغيل.
# أداة browser_screenshot تبقى تشتغل محلياً/عبر CLI كالمعتاد، وتفشل
# برسالة واضحة هنا لو استُخدمت من الشات المُستضاف — نفس سلوكها الصادق
# المعتاد، لا كسر صامت.
FROM python:3.11-slim

WORKDIR /app

COPY agent_os4/requirements.txt agent_os4/requirements.txt
RUN pip install --no-cache-dir -r agent_os4/requirements.txt

COPY agent_os4/ agent_os4/
COPY obsidian_vault.py obsidian_vault.py

ENV OS4_WEB_CHAT_PORT=8080
EXPOSE 8080

CMD ["python3", "-m", "agent_os4.web_chat"]
