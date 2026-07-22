from streamlit.testing.v1 import AppTest


def _nav_radio(app):
    """The sidebar navigation radio; main-body radios (e.g. impact queue) shift indices."""
    return next(radio for radio in app.radio if radio.key == "navigation")


def test_streamlit_project_workspace_and_project_navigation_have_no_exception():
    app = AppTest.from_file("app.py", default_timeout=15)
    app.run()
    assert not app.exception
    assert "你的研究项目" in [title.value for title in app.title]
    assert _nav_radio(app).options == [
        "项目工作台",
        "本周行动",
        "文献雷达",
        "改进工作台",
        "我的论文",
        "设置",
    ]
    assert app.selectbox[0].label == "当前项目"

    _nav_radio(app).set_value("本周行动").run()
    assert not app.exception
    assert "这个项目现在需要做什么？" in [title.value for title in app.title]
    assert any(metric.label == "紧急" for metric in app.metric)
    assert "有用论文" in [tab.label for tab in app.tabs]

    _nav_radio(app).set_value("文献雷达").run()
    assert not app.exception
    assert "搜索最新公开论文" in [title.value for title in app.title]

    _nav_radio(app).set_value("改进工作台").run()
    assert not app.exception
    assert "改进工作台" in [title.value for title in app.title]

    _nav_radio(app).set_value("设置").run()
    assert not app.exception
    assert "设置" in [title.value for title in app.title]
    assert any(button.label == "测试连接" for button in app.button)
