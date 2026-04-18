# PDF 渲染专项修复记录

日期: 2026-04-18

## 问题

- 前端 `PDF.js` 渲染中文 PDF 时出现丢字、错字和局部空白。
- 用户提供的 `AIA_2020_Annual_Report_zh.pdf` 实际页内正文与前端显示存在可见偏差风险。
- 前端缺少稳定的后端高保真预览兜底能力。

## 根因

### 1. `PDF.js` 缺少 CJK 字体映射资源

- `frontend/src/hooks/usePDFViewer.ts` 之前直接调用 `pdfjsLib.getDocument(url)`。
- `pdfjs-dist` 所需的 `cmaps` 和 `standard_fonts` 没有通过前端静态资源暴露给浏览器。
- `frontend/dev-server-4173.err.log` 中出现过明确告警:
  - `Ensure that the cMapUrl API parameter is provided`

### 2. 前端只有浏览器侧 PDF 渲染，没有后端预览兜底

- 当浏览器字体解析异常时，前端没有备用渲染链路。
- 对中文年报这类复杂字体 PDF，MVP 阶段需要一个更稳的后端按页预览能力。

## 修复

### 前端

- `usePDFViewer` 改为显式传入:
  - `cMapUrl`
  - `cMapPacked`
  - `standardFontDataUrl`
  - `useSystemFonts`
- 新增 `frontend/scripts/sync-pdfjs-assets.mjs`，将 `pdfjs-dist/cmaps` 和 `pdfjs-dist/standard_fonts` 同步到 `frontend/public/pdfjs`
- 在 `package.json` 中接入:
  - `sync:pdfjs-assets`
  - `predev`
  - `prebuild`
  - `prepreview`
  - `prepare`
- `PDFViewer` 新增图片模式，支持直接展示后端按页 PNG 预览
- 翻译执行页和审校页新增预览模式切换:
  - `后端高保真`
  - `PDF.js`
- 默认模式切换为 `后端高保真`

### 后端

- `backend_mock` 增加 `PyMuPDF`
- 新增接口:
  - `GET /api/v1/translations/{task_id}/preview?kind=source|target&page=N&dpi=144`
- 后端按页渲染 PNG，并写入 `backend_mock/storage/previews`
- 前端通过现有 `/api` 代理直接加载该预览图

## 验证

### 构建与测试

- `frontend npm run build` 通过
- `frontend npm run test:run` 通过，`56/56`
- `backend_mock/main.py` 语法校验通过

### 页面验证

- 重新上传 `AIA_2020_Annual_Report_zh.pdf`，新任务 `id=4`
- 定位用户截图对应正文页: 第 `10` 页
- 浏览器验证结果:
  - `后端高保真` 模式下，第 10 页正文完整显示
  - `PDF.js` 模式下，第 10 页正文显示与后端高保真一致，未再出现先前那种明显丢字
- `frontend/dev-server-4173.err.log` 在本轮验证后未再出现新的 `cMapUrl` / `font loading` 告警

## 当前结论

- 这次 PDF 丢字问题的主因已经确认并修复: `PDF.js` 资源链路缺失。
- 前端现在有两条可用渲染链路:
  - 修复后的 `PDF.js`
  - 后端高保真 PNG 预览
- 对 MVP 来说，默认走后端高保真预览更稳，`PDF.js` 保留为可切换模式。

## 残余风险

- 后端高保真预览本质是图片流，不具备原生 PDF 文本选择能力。
- 大页数 PDF 在高 DPI 下会增加服务端渲染和网络传输开销。
- `TranslationExecution` 和 `ComparisonReview` 页面中仍有历史中文文案编码问题，需要后续单独清理。
