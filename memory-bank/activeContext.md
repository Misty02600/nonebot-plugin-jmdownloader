# Active Context

## 当前工作重点
Memory Bank 初始化完成，项目处于稳定运行状态。

## 最近变更
- 2026-01-23: 初始化建立 Memory Bank 结构
  - 创建所有核心文档
  - 分析现有代码结构
  - 记录项目架构和技术栈

## 当前状态
- 项目版本: 1.0.4
- 分支: dev
- 状态: 功能完整，可正常使用

## 活跃决策

### 已确定的设计决策
1. **仅支持 OneBot V11**: 因群文件 API 的特殊性，暂不支持其他协议
2. **JSON 数据存储**: 使用单一 JSON 文件存储所有配置和状态
3. **用户次数限制**: 默认每周 5 次下载限制，防止滥用
4. **预置内容过滤**: 内置常见敏感标签过滤列表

### 待考虑的改进
- [ ] 考虑添加更多协议适配器支持
- [ ] 考虑使用数据库替代 JSON 存储
- [ ] 考虑添加更多自定义选项

## 下一步计划
1. 维护现有功能稳定性
2. 根据用户反馈进行优化
3. 定期更新依赖版本

## 注意事项
- 修改代码时注意异步处理模式
- 新增命令需考虑权限控制
- 涉及内容过滤的修改需谨慎
- 测试时注意 Mock 外部 API 调用

## 相关文件
- 主入口: [src/nonebot_plugin_jmdownloader/__init__.py](../src/nonebot_plugin_jmdownloader/__init__.py)
- 配置: [src/nonebot_plugin_jmdownloader/config.py](../src/nonebot_plugin_jmdownloader/config.py)
- 数据管理: [src/nonebot_plugin_jmdownloader/data_source.py](../src/nonebot_plugin_jmdownloader/data_source.py)
- 工具函数: [src/nonebot_plugin_jmdownloader/utils.py](../src/nonebot_plugin_jmdownloader/utils.py)
