set windows-shell := ["powershell", "-NoProfile", "-Command"]

# 默认任务列表
default:
    @just --list

# 运行测试
test:
    uv run pytest --cov=src --cov-report xml --junitxml=./junit.xml -n auto

# 版本发布（更新版本号、更新 lock 文件）
bump:
    uv run cz bump
    uv lock

# 生成 changelog
changelog:
    uv run git-cliff --latest

# 安装 pre-commit hooks
hooks:
    uv run prek install

# 代码检查
lint:
    uv run ruff check . --fix

# 代码格式化
format:
    uv run ruff format .

# 类型检查
check:
    uv run basedpyright

# 更新 pre-commit hooks
update:
    uv run prek auto-update
