# AI翻译系统 Mock 后端

简单的FastAPI Mock服务，用于前端开发测试。

## 功能

- ✅ 任务CRUD操作
- ✅ 任务控制（启动、暂停、恢复、取消）
- ✅ SSE事件流推送进度
- ✅ Mock PDF文件返回
- ✅ 统计信息

## 安装

```bash
pip install -r requirements.txt
```

## 运行

```bash
python main.py
```

服务将在 http://localhost:8000 启动

## API文档

启动后访问：http://localhost:8000/docs

## 主要接口

- `GET /api/tasks` - 获取任务列表
- `POST /api/tasks` - 创建任务
- `GET /api/tasks/{id}` - 获取任务详情
- `POST /api/tasks/{id}/start` - 启动任务
- `POST /api/tasks/{id}/pause` - 暂停任务
- `POST /api/tasks/{id}/resume` - 恢复任务
- `POST /api/tasks/{id}/cancel` - 取消任务
- `GET /api/tasks/{id}/events` - SSE事件流
- `GET /api/stats` - 统计信息

## 注意

- 所有上传的文件都会返回固定的Mock PDF（AIA 2020年报）
- SSE事件流会模拟6个翻译阶段，每个阶段2秒
- 数据存储在内存中，重启后丢失
