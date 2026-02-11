set windows-shell := ["powershell", "-NoProfile", "-Command"]

# 默认任务列表
default:
    @just --list

# 运行   nonebot
run:
    uv run nbr run --reload

# 运行测试
test:
    uv run pytest
# 版本发布（更新版本号、更新 lock 文件）
bump:
    uv run cz bump
    uv lock
    git push origin --force-with-lease

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

# 从 dev 向 main 创建 PR
pr:
    gh pr create --base main --fill
    gh pr view --web

# PR 合并后同步 dev 到 main
sync:
    git fetch origin
    git checkout dev
    git reset --hard origin/main
    git push origin dev --force-with-lease
