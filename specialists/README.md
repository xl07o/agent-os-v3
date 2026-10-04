# specialists/ — شخصيات خبراء جاهزة

282 شخصية "subagent" جاهزة من مشروع **The Agency**
(<https://github.com/msitarzewski/agency-agents>)، مرخّصة MIT (انظر
`LICENSE_agency-agents.txt`). كل ملف `.md` فيه frontmatter بسيط
(`name`, `description`, ...) متبوع بنص الشخصية الكامل (دورها، أسلوبها،
مهمتها).

هذا هو تطبيق فعلي لجزء "يكون مثقف بكل المجالات" من تصميم `agent_os3`:
بدل ما يكون عقل الوكيل عام دايماً، يقدر يستعير نص شخصية خبير متخصص
(مطور Frontend، محلل مالي، مؤرخ، ...إلخ) كـ system prompt مؤقت لسؤال
محدد، عبر `specialists.py`.

## الاستخدام البرمجي

```python
import specialists
specialists.find("frontend")          # يرجع أقرب الشخصيات تطابقاً
specialists.ask("Frontend Developer", "كيف أحسّن Core Web Vitals؟")
```

## من الدردشة

```
//خبير frontend :: كيف أحسّن سرعة الموقع؟
```

يفصل الاسم/الكلمة المفتاحية عن السؤال بـ `::`. لو ما لقى تطابق واضح،
يرجع أقرب 5 اقتراحات بدل ما يخمّن.
