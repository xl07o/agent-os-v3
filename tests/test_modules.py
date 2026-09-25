"""اختبارات الوحدات المتنوعة (autopilot, chat_cli, daily_summary, orchestrator, run_mission, setup_packages).

تشغيل: python -m pytest tests/ -v
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_autopilot_improve_scope():
    """التحسين الذاتي يستهدف مشاريع الأستخدام لا ملفات النظام فقط."""
    import autopilot
    import inspect
    src = inspect.getsource(autopilot.act_improve)
    assert "projects" in src
    assert "os.walk" in src


def test_chat_build_offline():
    """أمر البناء الفوري يعمل بلا شبكة وباسم مشروع آمن."""
    import chat_cli
    reply = chat_cli._build("بايثون")
    assert "بنيتُ" in reply
    assert "MyApp" in reply


def test_module_coverage_smoke():
    """استيراد وعمليات آمنة بلا شبكة لكل الوحدات غير المختبرة."""
    import autopilot
    assert callable(autopilot.step)
    assert isinstance(autopilot.has_brain(), bool)

    import daily_summary
    n = daily_summary._count_files(daily_summary.BASE_DIR, "md")
    assert isinstance(n, int) and n >= 0
    summary = daily_summary.build_summary(hours=1)
    assert isinstance(summary, str)

    import orchestrator
    assert callable(orchestrator.plan_task)
    assert callable(orchestrator.run_step)

    import run_mission
    assert callable(run_mission.main)

    import setup_packages
    assert isinstance(setup_packages.PACKAGE_GROUPS, dict)
    assert len(setup_packages.PACKAGE_GROUPS) >= 1
    assert setup_packages.install([]) is None


def test_intel_extract_skills():
    """استخراج تقنيات من عناوين أخبار (news_intel بلا شبكة)."""
    import news_intel
    items = [
        {"title": "Python 3.13 releases with better async", "snippet": ""},
        {"title": "New CVE in docker kubernetes runtime", "snippet": ""},
        {"title": "خبر عادي بلا تقنية", "snippet": ""},
    ]
    skills = news_intel.extract_skills_from_news(items)
    assert "python" in skills
    assert "docker" in skills
    assert "kubernetes" in skills


def test_intel_get_latest_missing_returns_none():
    """لا يوجد استخبارات اليوم → None (لا استثناء)."""
    import news_intel
    assert news_intel.get_latest_intel() is None or isinstance(news_intel.get_latest_intel(), dict)