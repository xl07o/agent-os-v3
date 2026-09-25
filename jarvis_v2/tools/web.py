# -*- coding: utf-8 -*-
"""أداة شبكة بسيطة بلا اعتمادات — جلب عنوان وقراءة نصه. تُستخدم للاستعلام ما بعد الإنشاء."""
import re
import urllib.request
from urllib.error import HTTPError, URLError

from .. import config

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; jarvis-v2-research)"}

def fetch_url(args):
    url = args.get("url") if isinstance(args, dict) else args
    if not url or not str(url).startswith(("http://", "https://")):
        return {"ok": False, "error": "عنوان غير صالح (تبدأ بـ http/https)"}
    try:
        req = urllib.request.Request(url, headers=UA)
        r = urllib.request.urlopen(req, timeout=config.FETCH_TIMEOUT)
        data = r.read(config.MAX_FILE_BYTES + 1).decode("utf-8", "replace")
        r.close()
        text = re.sub(r"\s+", " ", data)[:4000]
        return {"ok": True, "url": url, "bytes": len(data),
                "note": "جُلبت الصفحة", "content": text}
    except HTTPError as e:
        return {"ok": False, "error": "HTTP %d" % e.code}
    except URLError as e:
        return {"ok": False, "error": "شبكة: %s" % str(e.reason)[:150]}
    except Exception as ex:
        return {"ok": False, "error": str(ex)[:200]}