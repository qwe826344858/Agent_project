"""HTML 清洗模块单元测试"""

import pytest
from app.services.html_cleaner import clean_html, _truncate_text, MAX_CN_CHARS


class TestCleanHtml:
    """clean_html 函数测试"""

    def test_remove_script_tags(self):
        """script 标签及其内容应被完全删除"""
        html = '<html><body><p>正文</p><script>alert(1)</script></body></html>'
        text, _ = clean_html(html)
        assert "alert" not in text
        assert "正文" in text

    def test_remove_style_tags(self):
        """style 标签及其内容应被完全删除"""
        html = '<html><body><p>内容</p><style>.red{color:red}</style></body></html>'
        text, _ = clean_html(html)
        assert "color" not in text
        assert "red" not in text
        assert "内容" in text

    def test_remove_nav_footer(self):
        """nav 和 footer 标签内容应被删除"""
        html = (
            '<html><body>'
            '<nav><a href="/">首页导航</a></nav>'
            '<div><p>主要内容区</p></div>'
            '<footer><p>版权信息2024</p></footer>'
            '</body></html>'
        )
        text, _ = clean_html(html)
        assert "首页导航" not in text
        assert "版权信息" not in text
        assert "主要内容区" in text

    def test_preserve_content_text(self):
        """正文标签中的文本应被完整保留"""
        html = '<p>保障详情</p><div>300万</div><span>意外险</span>'
        text, _ = clean_html(html)
        assert "保障详情" in text
        assert "300万" in text
        assert "意外险" in text

    def test_cn_char_count(self):
        """中文字符计数应准确"""
        html = '<p>你好世界</p>'
        text, cn_count = clean_html(html)
        assert cn_count == 4
        assert "你好世界" in text

    def test_cn_char_count_mixed(self):
        """中英混合文本的中文字符计数"""
        html = '<p>Hello你好World世界Test测试</p>'
        _, cn_count = clean_html(html)
        # 你、好、世、界、测、试 = 6 个中文字符
        assert cn_count == 6

    def test_empty_html(self):
        """空字符串应返回 ("", 0)"""
        text, cn_count = clean_html("")
        assert text == ""
        assert cn_count == 0

    def test_empty_whitespace_html(self):
        """纯空白字符串也应返回 ("", 0)"""
        text, cn_count = clean_html("   \n\t  ")
        assert text == ""
        assert cn_count == 0

    def test_none_html(self):
        """None 输入应返回 ("", 0)"""
        text, cn_count = clean_html(None)
        assert text == ""
        assert cn_count == 0

    def test_merge_blank_lines(self):
        """连续多个空行应合并为最多 2 个换行"""
        html = '<p>第一段</p><br><br><br><br><br><p>第二段</p>'
        text, _ = clean_html(html)
        # 不应出现 3 个及以上连续换行
        assert '\n\n\n' not in text
        assert "第一段" in text
        assert "第二段" in text

    def test_truncate_long_text(self):
        """超过 5000 中文字符的文本应被截断"""
        # 构造超过 5000 中文字符的 HTML
        long_cn_text = "测" * 6000
        html = f'<p>{long_cn_text}</p>'
        text, cn_count = clean_html(html)
        assert cn_count == 6000
        # 截断后文本长度应小于原始长度
        assert len(text) < len(long_cn_text)

    def test_truncate_very_long_text_head_tail(self):
        """超过 10000 中文字符的文本应保留头部和尾部"""
        # 构造超过 10000 中文字符的 HTML，头尾用不同字符区分
        head_text = "头" * 5500
        mid_text = "中" * 3000
        tail_text = "尾" * 3000
        html = f'<p>{head_text}{mid_text}{tail_text}</p>'
        text, cn_count = clean_html(html)
        assert cn_count == 11500
        # 应包含截断标记
        assert "中间内容省略" in text
        # 头部内容应存在
        assert "头" in text
        # 尾部内容应存在
        assert "尾" in text

    def test_remove_multiple_noise_tags(self):
        """同时包含多种噪音标签的 HTML 应被正确清理"""
        html = (
            '<html><head><meta charset="utf-8"><link rel="stylesheet" href="a.css"></head>'
            '<body>'
            '<header><h1>网站标题</h1></header>'
            '<iframe src="ad.html"></iframe>'
            '<noscript>请启用 JavaScript</noscript>'
            '<svg><circle r="10"/></svg>'
            '<img src="photo.jpg" alt="照片">'
            '<div>保险产品详情</div>'
            '</body></html>'
        )
        text, _ = clean_html(html)
        assert "网站标题" not in text
        assert "JavaScript" not in text
        assert "保险产品详情" in text
