"""tests.fuzz — property-based / fuzz 测试包。

存在理由：避免与 tests/services/test_*.py 同名模块的 Python module cache 冲突。
（pytest 把 tests/fuzz 和 tests/services 视为 rootdir 子目录，模块名都是 test_*。）"""
