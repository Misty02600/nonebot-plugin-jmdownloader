# Tech Context

## 技术栈

### 核心框架
- **Python**: 3.11+ (使用 StrEnum、match case 等现代特性)
- **NoneBot2**: 2.4.2+ (异步机器人框架)
- **OneBot V11**: QQ 协议适配器

### 关键依赖

| 包名     | 版本范围        | 用途                   |
| -------- | --------------- | ---------------------- |
| jmcomic  | >=2.6.0         | JMComic API 和下载功能 |
| pyzipper | >=0.3.6         | ZIP AES 加密（可选）   |
| httpx    | >=0.27.0,<1.0.0 | 异步 HTTP 请求         |
| pillow   | >=11.1.0        | 图片处理（模糊效果）   |
| img2pdf  | >=0.6.0         | PDF 生成               |
| pydantic | (via nonebot2)  | 配置验证               |

### NoneBot2 插件依赖

| 插件                       | 用途                 |
| -------------------------- | -------------------- |
| nonebot-plugin-localstore  | 本地数据存储路径管理 |
| nonebot-plugin-apscheduler | 定时任务（缓存清理） |
| nonebot-plugin-alconna     | 命令解析增强         |
| nonebot-plugin-waiter      | 用户交互等待         |
| nonebot-plugin-uninfo      | 会话信息获取         |

## 开发环境

### 包管理
- **uv**: 主要包管理器
- **pyproject.toml**: 项目配置和依赖声明

### 代码质量
- **ruff**: 代码格式化和 linting
- **basedpyright**: 类型检查
- **pytest**: 单元测试

### 版本控制
- **commitizen**: 规范化提交
- **git-cliff**: 变更日志生成

## 项目结构

```
nonebot-plugin-jmdownloader/
├── src/
│   └── nonebot_plugin_jmdownloader/
│       ├── __init__.py      # 主入口，命令处理
│       ├── config.py        # 配置定义
│       ├── data_source.py   # 数据管理
│       └── utils.py         # 工具函数
├── tests/
│   ├── conftest.py          # 测试配置
│   └── plugin_test.py       # 插件测试
├── memory-bank/             # Memory Bank 文档
├── pyproject.toml           # 项目配置
├── justfile                 # 任务自动化
└── cliff.toml               # changelog 配置
```

## 配置项

### 环境变量配置 (.env)

| 配置项                   | 类型 | 默认值 | 说明                      |
| ------------------------ | ---- | ------ | ------------------------- |
| JMCOMIC_LOG              | bool | False  | JMComic 日志开关          |
| JMCOMIC_PROXIES          | str  | system | 代理配置                  |
| JMCOMIC_THREAD_COUNT     | int  | 10     | 下载线程数                |
| JMCOMIC_USERNAME         | str  | None   | JM 登录用户名             |
| JMCOMIC_PASSWORD         | str  | None   | JM 登录密码               |
| JMCOMIC_ALLOW_GROUPS     | bool | False  | 默认启用所有群            |
| JMCOMIC_OUTPUT_FORMAT    | str  | pdf    | 输出格式：pdf 或 zip      |
| JMCOMIC_ZIP_PASSWORD     | str  | None   | ZIP 加密密码（需 pyzipper）|
| JMCOMIC_USER_LIMITS      | int  | 5      | 每周下载限制              |
| JMCOMIC_MODIFY_REAL_MD5  | bool | False  | 修改 PDF MD5（仅PDF有效） |
| JMCOMIC_RESULTS_PER_PAGE | int  | 20     | 搜索分页数量              |

## 数据存储

### 缓存目录
- 由 `nonebot_plugin_localstore` 管理
- 存储下载的 PDF/ZIP/7Z 文件
- 每日凌晨 3 点自动清理

### 数据文件 (jmcomic_data.json)
```json
{
    "restricted_tags": ["tag1", "tag2"],
    "restricted_ids": ["123456"],
    "user_limits": {
        "用户ID": 剩余次数
    },
    "群ID": {
        "folder_id": "文件夹ID",
        "enabled": true,
        "blacklist": ["用户ID"]
    }
}
```

## 技术约束

1. **协议限制**: 仅支持 OneBot V11，因群文件 API 特殊性
2. **Python 版本**: 需要 3.11+ 以使用 StrEnum 和 match case 语法
3. **网络要求**: 需能访问 JMComic 服务（可配置代理）
4. **存储空间**: 需要足够空间缓存 PDF 文件

## 构建与发布

### 构建系统
- 使用 `uv_build` 作为构建后端

### 发布渠道
- PyPI: `nonebot-plugin-jmdownloader`
- GitHub: `Misty02600/nonebot-plugin-jmdownloader`

### 版本管理
- 语义化版本 (SemVer)
- 当前版本: 1.0.4
